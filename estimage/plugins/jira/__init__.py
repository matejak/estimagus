import dataclasses
import datetime
import collections
import time
import typing

from jira import JIRA, exceptions

from ...entities import card
from ... import simpledata
from ...entities import event as evts
from ... import simpledata


JIRA_STATUS_TO_STATE = {
    "Backlog": "todo",
    "Refinement": "todo",
    "New": "todo",
    "Done": "done",
    "Verified": "done",
    "Abandoned": "irrelevant",
    "Closed": "irrelevant",
    "In Progress": "in_progress",
    "ASSIGNED": "in_progress",
    "ON_DEV": "in_progress",
    "POST": "in_progress",
    "MODIFIED": "in_progress",
    "Needs Peer Review": "review",
    "To Do": "todo",
}


JIRA_PRIORITY_TO_VALUE = {
    "Blocker": 90,
    "Critical": 80,
    "Major": 70,
    "Normal": 50,
    "Minor": 30,
}


Collected = collections.namedtuple("Collected", ("Retrospective", "Projective", "Events"))


class CardSynchronizer:
    def __init__(self, server_url, token, importer_cls, ** kwargs):
        self.server_url = server_url
        self.token = token
        self.importer_cls = importer_cls
        super().__init__(** kwargs)

    @classmethod
    def from_form(cls, form):
        raise NotImplementedError

    def _get_spec(self):
        ret = InputSpec()
        ret.server_url = self.server_url
        ret.token = self.token
        ret.item_class = card.BaseCard
        return ret

    def get_tracker_points_of(self, c: card.BaseCard) -> float:
        spec = self._get_spec()
        spec.item_class = c.__class__
        importer = self.importer_cls(spec)
        return importer.get_points_of(c)

    def insert_points_into_tracker(self, c: card.BaseCard, target_points: float):
        spec = self._get_spec()
        spec.item_class = c.__class__
        importer = self.importer_cls(spec)
        importer.update_points_of(c, target_points)


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
        ret.item_class = app.config["classes"]["BaseCard"]
        return ret


def jira_retry(func, * args, ** kwargs):
    return jira_retry_n(5, 2, func, * args, ** kwargs)


def jira_retry_n(retries, pause, func, * args, ** kwargs):
    try:
        result = func(* args, ** kwargs)
    except exceptions.JIRAError:
        if retries <= 0:
            raise
        time.sleep(pause)
        print(f"Failed {func.__name__}, retrying {retries} more times")
        result = jira_retry_n(retries - 1, pause, func, * args, ** kwargs)
    return result


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


def save_exported_jira_tasks(all_cards_by_id, id_selection, card_io_class):
    to_save = [all_cards_by_id[tid] for tid in id_selection]
    card_io_class.bulk_save_metadata(to_save)


def jira_datetime_to_datetime(jira_datetime):
    date_str = jira_datetime.split("+")[0]
    return datetime.datetime.fromisoformat(date_str)


def jira_date_to_datetime(jira_date):
    return datetime.datetime.strptime(jira_date, "%Y-%m-%d")


class EventExtractor:
    STORY_POINTS = "customfield_12310243"

    def __init__(self, task, cutoff_date=None):
        self.task = task
        self.cutoff_datetime = None
        if cutoff_date:
            self.cutoff_datetime = datetime.datetime(
                cutoff_date.year, cutoff_date.month, cutoff_date.day)
        self.importer = Importer

    def get_histories(self):
        return [
            history for history in self.task.changelog.histories
            if jira_datetime_to_datetime(history.created) >= self.cutoff_datetime
        ]

    def import_event(self, event, date):

        field_name = event.field
        former_value = event.fromString
        new_value = event.toString
        related_task_name = self.task.key

        evt = None
        if field_name == "status":
            evt = evts.Event(related_task_name, "state", date)
            evt.value_before = self.importer.status_to_state(self.task, former_value)
            evt.value_after = self.importer.status_to_state(self.task, new_value)
            evt.msg = f"Status changed from '{former_value}' to '{new_value}'"
        elif field_name == self.STORY_POINTS:
            evt = evts.Event(related_task_name, "points", date)
            evt.value_before = float(former_value or 0)
            evt.value_after = float(new_value or 0)
            evt.msg = f"Points changed from {former_value} to {new_value}"
        elif field_name in ("Latest Status Summary", "Status Summary"):
            evt = evts.Event(related_task_name, "status_summary", date)
            evt.value_before = former_value
            evt.value_after = new_value
            evt.msg = f"Event summary changed to {new_value}"

        return evt

    def append_event_entry(self, events, event, date):
        event = self.import_event(event, date)
        if event is not None:
            events.append(event)
        return events

    def get_events_from_task_histories(self, histories):
        events = []
        for history in histories:
            date = jira_datetime_to_datetime(history.created)

            for event in history.items:
                self.append_event_entry(events, event, date)
        return events

    def get_task_events(self, importer=None):
        if importer:
            self.importer = importer
        recent_enough_histories = self.get_histories()
        events = self.get_events_from_task_histories(recent_enough_histories)
        return events


class JiraWithRetry(JIRA):
    def search_issues(self, * args, ** kwargs):
        return jira_retry(super().search_issues, * args, ** kwargs)

    def issue(self, * args, ** kwargs):
        return jira_retry(super().issue, * args, ** kwargs)


class Importer:
    def __init__(self, spec):
        self._cards_by_id = dict()
        self._all_issues_by_name = dict()
        self._parents_child_keymap = collections.defaultdict(set)

        self._retro_cards = set()
        self._projective_cards = set()
        self._all_events = []
        try:
            self.jira = JiraWithRetry(spec.server_url, token_auth=spec.token, validate=True)
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
            new_cards = self.export_jira_epic_chain_to_cards(retro_epic_names)
            self._retro_cards.update(new_cards.keys())
            issue_names_requiring_events.update(new_cards.keys())
            self._cards_by_id.update(new_cards)

        proj_epic_names = set()
        if spec.projective_query:
            self.report("Gathering proj stuff")
            proj_epic_names = get_epics_and_their_tasks_by_id(
                self.jira, spec.projective_query, self._all_issues_by_name,
                self._parents_child_keymap)
            new_names = proj_epic_names.difference(retro_epic_names)
            new_cards = self.export_jira_epic_chain_to_cards(new_names)
            known_names = proj_epic_names.intersection(retro_epic_names)
            known_cards = self.export_jira_epic_chain_to_cards(known_names)
            self._cards_by_id.update(new_cards)
            self._projective_cards.update(new_cards.keys())
            self._projective_cards.update(known_cards.keys())

        self.resolve_inheritance(proj_epic_names.union(retro_epic_names))

        for name in issue_names_requiring_events:
            extractor = EventExtractor(self._all_issues_by_name[name], spec.cutoff_date)
            new_events = extractor.get_task_events(self)
            self._all_events.extend(new_events)



    def find_cards(self, card_names: typing.Iterable[str]):
        card_ids_sequence = ", ".join(card_names)
        query = f"id in ({card_ids_sequence})"
        cards = self.jira.search_issues(query, expand="renderedFields")
        cards_by_id = {t.key: t for t in cards}
        return [cards_by_id[name] for name in card_names]

    def find_card(self, name: str):
        card = self.jira.issue(name)
        if not card:
            msg = (
                f"{card} not found"
            )
            raise ValueError(msg)
        return card

    def refresh_cards(self, real_cards: typing.Iterable[card.BaseCard], io_cls):
        if not real_cards:
            return
        fresh = self.find_cards([t.name for t in real_cards])
        refreshed = [self._apply_refresh(real, jira) for real, jira in zip(real_cards, fresh)]
        io_cls.bulk_save_metadata(refreshed)

    def _get_refreshed_card(self, real_card: card.BaseCard):
        jira_card = self.jira.issue(real_card.name, expand="renderedFields")
        return self._apply_refresh(real_card, jira_card)

    def _apply_refresh(self, real_card: card.BaseCard, jira_card):
        fresh_card = self.merge_jira_item_without_children(jira_card)
        fresh_card.children = real_card.children
        return fresh_card

    def export_jira_epic_chain_to_cards(self, root_names: typing.Iterable[str]) -> dict[str, card.BaseCard]:
        exported_cards_by_id = dict()
        for name in root_names:
            if name in self._cards_by_id:
                card = self._cards_by_id[name]
            else:
                issue = self._all_issues_by_name[name]
                card = self.merge_jira_item_without_children(issue)
            exported_cards_by_id[name] = card
            children = self._parents_child_keymap[name]
            if not children:
                continue
            chain = self.export_jira_epic_chain_to_cards(children)
            exported_cards_by_id.update(chain)
        return exported_cards_by_id

    def resolve_inheritance(self, root_names: typing.Iterable[str]):
        for root_name in root_names:
            resolve_inheritance_of_attributes(
                root_name, self._cards_by_id, self._parents_child_keymap)

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
        ret = cls._status_to_state(item, jira_string)
        return ret

    @classmethod
    def _status_to_state(cls, item, jira_string):
        resolution = item.get_field("resolution")
        resolution_text = ""
        if resolution:
            resolution_text = resolution.name
        if jira_string == "Closed" and resolution_text == "Done":
            jira_string = "Done"
        return JIRA_STATUS_TO_STATE.get(jira_string, "irrelevant")

    def merge_jira_item_without_children(self, item):
        result = self.item_class(item.key)
        result.uri = item.permalink()
        result.loading_plugin = "jira"
        result.title = item.get_field("summary") or ""
        result.description = self._get_contents_of_rendered_field(item, "description")
        result.status = self.status_to_state(item)
        if item.fields.issuetype.name == "Epic" and result.status == "abandoned":
            result.status = "done"
        priority = item.get_field("priority")
        if not priority:
            result.priority = 0
        else:
            result.priority = JIRA_PRIORITY_TO_VALUE.get(priority.name, 0)
        result.tags = {f"label:{value}" for value in (item.get_field("labels") or [])}

        if assignee := item.get_field("assignee"):
            result.assignee = name_from_field(assignee)

        return result

    def save(self, retro_card_io_class, proj_card_io_class, event_manager_class):
        if self._retro_cards:
            retro_card_io_class.forget_all()
            save_exported_jira_tasks(self._cards_by_id, self._retro_cards, retro_card_io_class)
        if self._projective_cards:
            proj_card_io_class.forget_all()
            save_exported_jira_tasks(self._cards_by_id, self._projective_cards, proj_card_io_class)

        storer = event_manager_class()
        for e in self._all_events:
            storer.add_event(e)
        storer.save()

    def get_collected_stats(self):
        ret = Collected(
            Retrospective=len(self._retro_cards),
            Projective=len(self._projective_cards),
            Events=len(self._all_events),
        )
        return ret


def _convert_stats_to_strings(stats):
    pieces = []
    if r := stats.Retrospective:
        pieces.append(f"{r} retrospective items")
    if p := stats.Projective:
        pieces.append(f"{p} planning items")
    if e := stats.Events:
        pieces.append(f"{e} events")
    return pieces


def _format_string_stats_into_sentence(pieces):
    if not pieces:
        return "Collected nothing."
    fusion = ", ".join(pieces[:-1])
    if fusion:
        fusion = f"{fusion} and {pieces[-1]}"
    else:
        fusion = pieces[-1]
    return f"Collected {fusion}."


def stats_to_summary(stats):
    pieces = _convert_stats_to_strings(stats)
    return _format_string_stats_into_sentence(pieces)


def do_stuff(spec):
    importer = Importer(spec)
    importer.import_data(spec)
    retro_io = web_utils.get_retro_loader()[1]
    proj_io = web_utils.get_proj_loader()[1]
    importer.save(retro_io, proj_io, simpledata.EventManager)
    return importer.get_collected_stats()
