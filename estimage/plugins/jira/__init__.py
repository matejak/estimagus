import dataclasses
import datetime
import collections
import typing

from jira import JIRA, exceptions

from ...entities import target
from ... import simpledata
from ...entities import event as evts


JIRA_STATUS_TO_STATE = {
    "Backlog": target.State.todo,
    "Refinement": target.State.todo,
    "New": target.State.todo,
    "Done": target.State.done,
    "Verified": target.State.done,
    "Abandoned": target.State.abandoned,
    "Closed": target.State.abandoned,
    "In Progress": target.State.in_progress,
    "ASSIGNED": target.State.in_progress,
    "ON_DEV": target.State.in_progress,
    "POST": target.State.in_progress,
    "MODIFIED": target.State.in_progress,
    "Needs Peer Review": target.State.review,
    "Review": target.State.review,
    "ON_QA": target.State.review,
    "To Do": target.State.todo,
}


JIRA_PRIORITY_TO_VALUE = {
    "Blocker": 90,
    "Critical": 80,
    "Major": 70,
    "Normal": 50,
    "Minor": 30,
}


Collected = collections.namedtuple("Collected", ("Retrospective", "Projective", "Events"))


@dataclasses.dataclass(init=False)
class InputSpec:
    token: str
    server_url: str
    retrospective_query: str
    projective_query: str
    cutoff_date: datetime.date
    item_class: typing.Type

    @classmethod
    def from_form_and_app(cls, input_form, app) -> "InputSpec":
        ret = cls()
        ret.token = input_form.token.data
        ret.server_url = input_form.server.data
        ret.retrospective_query = input_form.retroQuery.data
        ret.projective_query = input_form.projQuery.data
        ret.cutoff_date = input_form.cutoffDate.data
        ret.item_class = app.config["classes"]["BaseTarget"]
        return ret


def identify_epic_subtasks(jira, epic, known_issues_by_id, parents_child_keymap):
    subtasks = jira.search_issues(
        f'"Epic Link" = {epic.key}', expand="changelog,renderedFields", maxResults=0)
    for t in subtasks:
        parents_child_keymap[epic.key].add(t.key)
        if t.key in known_issues_by_id:
            continue
        known_issues_by_id[t.key] = t
        recursively_identify_task_subtasks(jira, t, known_issues_by_id, parents_child_keymap)


def recursively_identify_task_subtasks(jira, task, known_issues_by_id, parents_child_keymap):
    subtasks = task.get_field("subtasks")
    if not subtasks:
        return
    for subtask in subtasks:
        parents_child_keymap[task.key].add(subtask.key)
        if subtask.key in known_issues_by_id:
            continue
        subtask = jira.issue(subtask.key, expand="changelog,renderedFields")
        known_issues_by_id[subtask.key] = subtask
        recursively_identify_task_subtasks(jira, subtask, known_issues_by_id, parents_child_keymap)


def get_epics_and_their_tasks_by_id(jira, epics_query, all_items_by_name, parents_child_keymap):
    epics = jira.search_issues(
        f"type = epic AND {epics_query}", expand="changelog,renderedFields", maxResults=0)

    new_epics_names = set()
    for epic in epics:
        new_epics_names.add(epic.key)
        if epic.key in all_items_by_name:
            continue
        all_items_by_name[epic.key] = epic
        identify_epic_subtasks(jira, epic, all_items_by_name, parents_child_keymap)
    return new_epics_names


def name_from_field(field_contents):
    return field_contents.emailAddress.split("@", 1)[0]


def inherit_attributes(parent, child):
    parent.add_element(child)
    child.tier = parent.tier


def resolve_inheritance_of_attributes(name, all_items_by_id, parents_child_keymap):
    item = all_items_by_id[name]
    child_names = parents_child_keymap.get(item.name, [])
    for child_name in child_names:
        child = all_items_by_id[child_name]
        inherit_attributes(item, child)
        resolve_inheritance_of_attributes(child_name, all_items_by_id, parents_child_keymap)


def save_exported_jira_tasks(all_targets_by_id, id_selection, target_io_class):
    to_save = [all_targets_by_id[tid] for tid in id_selection]
    target_io_class.bulk_save_metadata(to_save)


def jira_datetime_to_datetime(jira_datetime):
    date_str = jira_datetime.split("+")[0]
    return datetime.datetime.fromisoformat(date_str)


def jira_date_to_datetime(jira_date):
    return datetime.datetime.strptime(jira_date, "%Y-%m-%d")


def import_event(event, date, related_task):
    STORY_POINTS = "customfield_12310243"

    field_name = event.field
    former_value = event.fromString
    new_value = event.toString
    related_task_name = related_task.key

    evt = None
    if field_name == "status":
        evt = evts.Event(related_task_name, "state", date)
        evt.value_before = Importer.status_to_state(related_task, former_value)
        evt.value_after = Importer.status_to_state(related_task, new_value)
        evt.msg = f"Status changed from '{former_value}' to '{new_value}'"
    elif field_name == STORY_POINTS:
        evt = evts.Event(related_task_name, "points", date)
        evt.value_before = float(former_value or 0)
        evt.value_after = float(new_value or 0)
        evt.msg = f"Points changed from {former_value} to {new_value}"
    elif field_name == "Latest Status Summary":
        evt = evts.Event(related_task_name, "status_summary", date)
        evt.value_before = former_value
        evt.value_after = new_value
        evt.msg = f"Event summary changed to {new_value}"

    return evt


def append_event_entry(events, event, date, related_task):
    event = import_event(event, date, related_task)
    if event is not None:
        events.append(event)
    return events


def get_events_from_relevant_task_histories(histories, task):
    events = []
    for history in histories:
        date = jira_datetime_to_datetime(history.created)

        for event in history.items:
            append_event_entry(events, event, date, task)
    return events


def get_task_events(task, cutoff_date):
    cutoff_datetime = None
    if cutoff_date:
        cutoff_datetime = datetime.datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day)

    recent_enough_histories = [
        history for history in task.changelog.histories
        if jira_datetime_to_datetime(history.created) >= cutoff_datetime
    ]

    events = get_events_from_relevant_task_histories(recent_enough_histories, task)
    return events


class Importer:
    def __init__(self, spec):
        self._targets_by_id = dict()
        self._all_issues_by_name = dict()
        self._parents_child_keymap = collections.defaultdict(set)

        self._retro_targets = set()
        self._projective_targets = set()
        self._all_events = []
        try:
            self.jira = JIRA(spec.server_url, token_auth=spec.token, validate=True)
        except exceptions.JIRAError as exc:
            msg = f"Error establishing a Jira session: {exc.text}"
            raise RuntimeError(msg) from exc
        self.item_class = spec.item_class

    def report(self, msg):
        print(msg)

    def import_data(self, spec):
        issue_names_requiring_events = set()

        retro_epic_names = set()
        if spec.retrospective_query:
            self.report("Gathering retro stuff")
            retro_epic_names = get_epics_and_their_tasks_by_id(
                self.jira, spec.retrospective_query, self._all_issues_by_name,
                self._parents_child_keymap)
            new_targets = self.export_jira_epic_chain_to_targets(retro_epic_names)
            self._retro_targets.update(new_targets.keys())
            issue_names_requiring_events.update(new_targets.keys())
            self._targets_by_id.update(new_targets)

        proj_epic_names = set()
        if spec.projective_query:
            self.report("Gathering proj stuff")
            proj_epic_names = get_epics_and_their_tasks_by_id(
                self.jira, spec.projective_query, self._all_issues_by_name,
                self._parents_child_keymap)
            new_names = proj_epic_names.difference(retro_epic_names)
            new_targets = self.export_jira_epic_chain_to_targets(new_names)
            known_names = proj_epic_names.intersection(retro_epic_names)
            known_targets = self.export_jira_epic_chain_to_targets(known_names)
            self._targets_by_id.update(new_targets)
            self._projective_targets.update(new_targets.keys())
            self._projective_targets.update(known_targets.keys())

        self.resolve_inheritance(proj_epic_names.union(retro_epic_names))

        for name in issue_names_requiring_events:
            new_events = get_task_events(self._all_issues_by_name[name], spec.cutoff_date)
            self._all_events.extend(new_events)

    def find_targets(self, target_names: typing.Iterable[str]):
        target_ids_sequence = ", ".join(target_names)
        query = f"id in ({target_ids_sequence})"
        targets = self.jira.search_issues(query, expand="renderedFields")
        targets_by_id = {t.key: t for t in targets}
        return [targets_by_id[name] for name in target_names]

    def find_target(self, name: str):
        query = f"id = {name}"
        target = self.jira.search_issues(query)
        if not target:
            msg = (
                f"{target} not found"
            )
            raise ValueError(msg)
        return target[0]

    def refresh_targets(self, real_targets: typing.Iterable[target.BaseTarget], io_cls):
        if not real_targets:
            return
        fresh = self.find_targets([t.name for t in real_targets])
        refreshed = [self._apply_refresh(real, jira) for real, jira in zip(real_targets, fresh)]
        io_cls.bulk_save_metadata(refreshed)

    def _get_refreshed_target(self, real_target: target.BaseTarget):
        jira_target = self.jira.issue(real_target.name, expand="renderedFields")
        return self._apply_refresh(real_target, jira_target)

    def _apply_refresh(self, real_target: target.BaseTarget, jira_target):
        fresh_target = self.merge_jira_item_without_children(jira_target)
        fresh_target.children = real_target.children
        return fresh_target

    def export_jira_epic_chain_to_targets(self, root_names: typing.Iterable[str]) -> dict[str, target.BaseTarget]:
        exported_targets_by_id = dict()
        for name in root_names:
            issue = self._all_issues_by_name[name]
            target = self.merge_jira_item_without_children(issue)
            exported_targets_by_id[name] = target
            children = self._parents_child_keymap[name]
            if not children:
                continue
            chain = self.export_jira_epic_chain_to_targets(children)
            exported_targets_by_id.update(chain)
        return exported_targets_by_id

    def resolve_inheritance(self, root_names: typing.Iterable[str]):
        for root_name in root_names:
            resolve_inheritance_of_attributes(
                root_name, self._targets_by_id, self._parents_child_keymap)

    def _get_contents_of_rendered_field(self, item, field_name):
        ret = ""
        try:
            ret = item.get_field(field_name) or ""
            ret = getattr(item.renderedFields, field_name)
        except AttributeError:
            pass
        ret = ret.replace("\r", "")
        return ret

    @classmethod
    def status_to_state(cls, item, jira_string=""):
        if not jira_string:
            jira_string = item.get_field("status").name
        return cls._status_to_state(item, jira_string)

    @classmethod
    def _status_to_state(cls, item, jira_string):
        return JIRA_STATUS_TO_STATE.get(jira_string, target.State.unknown)

    def merge_jira_item_without_children(self, item):
        result = self.item_class(item.key)
        result.uri = item.permalink()
        result.loading_plugin = "jira"
        result.title = item.get_field("summary") or ""
        result.description = self._get_contents_of_rendered_field(item, "description")
        result.state = self.status_to_state(item)
        if item.fields.issuetype.name == "Epic" and result.state == target.State.abandoned:
            result.state = target.State.done
        result.priority = JIRA_PRIORITY_TO_VALUE.get(item.get_field("priority").name, 0)
        result.tags = {f"label:{value}" for value in (item.get_field("labels") or [])}

        if assignee := item.get_field("assignee"):
            result.assignee = name_from_field(assignee)

        return result

    def save(self, retro_target_io_class, proj_target_io_class, event_manager_class):
        if self._retro_targets:
            retro_target_io_class.forget_all()
            save_exported_jira_tasks(self._targets_by_id, self._retro_targets, retro_target_io_class)
        if self._projective_targets:
            proj_target_io_class.forget_all()
            save_exported_jira_tasks(self._targets_by_id, self._projective_targets, proj_target_io_class)

        storer = event_manager_class()
        for e in self._all_events:
            storer.add_event(e)
        storer.save()

    def get_collected_stats(self):
        ret = Collected(
            Retrospective=len(self._retro_targets),
            Projective=len(self._projective_targets),
            Events=len(self._all_events),
        )
        return ret


def stats_to_summary(stats):
    pieces = []
    if r := stats.Retrospective:
        pieces.append(f"{r} retrospective items")
    if p := stats.Projective:
        pieces.append(f"{p} planning items")
    if e := stats.Events:
        pieces.append(f"{e} events")
    if not pieces:
        return ""
    fusion = ", ".join(pieces[:-1])
    if fusion:
        fusion = f"{fusion} and {pieces[-1]}"
    else:
        fusion = pieces[-1]
    return f"Collected {fusion}."


def do_stuff(spec, retro_io, proj_io):
    importer = Importer(spec)
    importer.import_data(spec)
    importer.save(retro_io, proj_io, simpledata.EventManager)
