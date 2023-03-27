import dataclasses
import datetime
import collections
import typing

from jira import JIRA

from estimage.entities import target
from estimage import simpledata
import estimage.entities.event as evts


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


@dataclasses.dataclass(init=False)
class InputSpec:
    token: str
    server_url: str
    retrospective_query: str
    projective_query: str
    cutoff_date: datetime.date

    @classmethod
    def from_dict(cls, input_form) -> "InputSpec":
        ret = cls()
        ret.token = input_form.token.data
        ret.server_url = input_form.server.data
        ret.retrospective_query = input_form.retroQuery.data
        ret.projective_query = input_form.projQuery.data
        ret.cutoff_date = input_form.cutoffDate.data
        return ret


def identify_epic_subtasks(jira, epic, known_issues_by_id, parents_child_keymap):
    subtasks = jira.search_issues(f'"Epic Link" = {epic.key}', expand="changelog,renderedFields", maxResults=0)
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
    epics = jira.search_issues(f"type = epic AND {epics_query}", expand="changelog,renderedFields", maxResults=0)

    new_epics_names = set()
    for epic in epics:
        new_epics_names.add(epic.key)
        if epic.key in all_items_by_name:
            continue
        all_items_by_name[epic.key] = epic
        identify_epic_subtasks(jira, epic, all_items_by_name, parents_child_keymap)
    return new_epics_names


def name_from_field(field_contents):
    return field_contents.name.split("@", 1)[0]


def merge_jira_item_without_children(result_class, item, all_items_by_id, parents_child_keymap):
    STORY_POINTS = "customfield_12310243"
    EPIC_LINK = "customfield_12311140"
    CONTRIBUTORS = "customfield_12315950"
    COMMITMENT = "customfield_12317404"
    STATUS_SUMMARY = "customfield_12317299"
    WORK_START = "customfield_12313941"
    WORK_END = "customfield_12313942"

    result = result_class()
    result.name = item.key
    result.uri = item.permalink()
    result.loading_plugin = "jira"
    result.title = item.get_field("summary") or ""
    result.description = item.get_field("description") or ""
    try:
        result.description = item.renderedFields.description.replace("\r", "")
    except Exception:
        pass
    result.point_cost = float(item.get_field(STORY_POINTS) or 0)
    result.state = JIRA_STATUS_TO_STATE.get(item.get_field("status").name, target.State.unknown)
    result.priority = JIRA_PRIORITY_TO_VALUE.get(item.get_field("priority").name, 0)
    result.status_summary = item.get_field(STATUS_SUMMARY) or ""
    try:
        result.status_summary = getattr(item.renderedFields, STATUS_SUMMARY).replace("\r", "")
    except Exception:
        pass
    result.tags = {f"label:{value}" for value in (item.get_field("labels") or [])}
    result.collaborators = []

    if assignee := item.get_field("assignee"):
        result.assignee = name_from_field(assignee)

    try:
        result.collaborators += [name_from_field(c) for c in item.get_field(CONTRIBUTORS) or []]
    except AttributeError:
        pass

    result.tier = 0
    try:
        if commitment_item := item.get_field(COMMITMENT):
            result.tags.add(f"commitment:{commitment_item.value.lower()}")
            if commitment_item.value.lower() == "planned":
                result.tier = 1
    except AttributeError:
        pass

    work_span = [None, None]
    if work_end := item.get_field(WORK_END):
        work_span[-1] = jira_date_to_datetime(work_end)

    if work_start := item.get_field(WORK_START):
        work_span[0] = jira_date_to_datetime(work_start)

    if work_span[0] or work_span[-1]:
        result.work_span = tuple(work_span)

    return result


def inherit_attributes(parent, child):
    parent.add_element(child)
    # if work_span := parent.work_span:
        # child.work_span = work_span


def resolve_inheritance_of_attributes(name, all_items_by_id, parents_child_keymap):
    item = all_items_by_id[name]
    child_names = parents_child_keymap.get(item.name, [])
    for child_name in child_names:
        child = all_items_by_id[child_name]
        inherit_attributes(item, child)
        resolve_inheritance_of_attributes(child_name, all_items_by_id, parents_child_keymap)


def export_jira_epic_chain_to_targets(root_names, all_issues_by_id, parents_child_keymap):
    all_targets_by_id = dict()
    for iid, issue in all_issues_by_id.items():
        all_targets_by_id[iid] = merge_jira_item_without_children(
            target.BaseTarget, issue, all_issues_by_id, parents_child_keymap)
    for root_name in root_names:
        resolve_inheritance_of_attributes(root_name, all_targets_by_id, parents_child_keymap)
    return all_targets_by_id


def save_exported_jira_tasks(all_targets_by_id, id_selection, target_class):
    for tid in id_selection:
        t = all_targets_by_id[tid].as_class(target_class)
        t.save_metadata()
        t.save_point_cost()
        t.save_time_cost()


def jira_datetime_to_datetime(jira_datetime):
    date_str = jira_datetime.split("+")[0]
    return datetime.datetime.fromisoformat(date_str)


def jira_date_to_datetime(jira_date):
    return datetime.datetime.strptime(jira_date, "%Y-%m-%d")


def import_event(event, date, related_task_name):
    STORY_POINTS = "customfield_12310243"
    EPIC_LINK = "customfield_12311140"
    STATUS_SUMMARY = "customfield_12317299"

    field_name = event.field
    former_value = event.fromString
    new_value = event.toString

    evt = None
    if field_name == "status":
        evt = evts.Event(related_task_name, "state", date)
        evt.value_before = JIRA_STATUS_TO_STATE.get(former_value, target.State.unknown)
        evt.value_after = JIRA_STATUS_TO_STATE.get(new_value, target.State.unknown)
        evt.msg = f"Status changed from '{former_value}' to '{new_value}'"
    elif field_name == STORY_POINTS:
        evt = evts.Event(related_task_name, "points", date)
        evt.value_before = float(former_value or 0)
        evt.value_after = float(new_value or 0)
        evt.msg = f"Points changed from {former_value} to {new_value}"
    elif field_name == EPIC_LINK:
        evt = evts.Event(related_task_name, "project", date)
        evt.value_before = int(former_value in sprint_epics)
        evt.value_after = int(new_value in sprint_epics)
        evt.msg = f"Got assigned epic {new_value}"
    elif field_name == "Latest Status Summary":
        evt = evts.Event(related_task_name, "status_summary", date)
        evt.value_before = former_value
        evt.value_after = new_value
        evt.msg = f"Event summary changed to {new_value}"

    return evt


def extract_status_updates(all_events):
    last_updates = dict()
    for e in all_events:
        if e.quantity == "status_summary":
            if (task_name := e.task_name) in last_updates:
                last_updates[task_name] = max(last_updates[task_name], e.time)
            else:
                last_updates[task_name] = e.time
    return last_updates


def apply_status_updates(issues_by_name, all_events):
    last_updates_by_id = extract_status_updates(all_events)
    for issue_name, date in last_updates_by_id.items():
        issues_by_name[issue_name].status_summary_time = date


def apply_some_events_into_issues(issues_by_name, all_events):
    apply_status_updates(issues_by_name, all_events)


def append_event_entry(events, event, date, related_task_name):
    event = import_event(event, date, related_task_name)
    if event is not None:
        events.append(event)
    return events


def get_task_events(task, cutoff_date, sprint_epics=frozenset()):
    cutoff_datetime = None
    if cutoff_date:
        cutoff_datetime = datetime.datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day)

    events = []
    for history in task.changelog.histories:
        date = jira_datetime_to_datetime(history.created)

        if cutoff_datetime and date < cutoff_datetime:
            continue

        for event in history.items:
            append_event_entry(events, event, date, task.key)

    return events


def import_targets_and_events(spec, retro_target_class, proj_target_class, event_manager_class):
    targets_by_id = dict()
    new_subtasks_by_id = dict()

    jira = JIRA(spec.server_url, token_auth=spec.token)
    parents_child_keymap = collections.defaultdict(set)
    all_issues_by_name = dict()
    issue_names_requiring_events = set()
    retro_targets = set()
    if spec.retrospective_query:
        retro_epic_names = get_epics_and_their_tasks_by_id(jira, spec.retrospective_query, all_issues_by_name, parents_child_keymap)
        new_targets = export_jira_epic_chain_to_targets(retro_epic_names, all_issues_by_name, parents_child_keymap)
        retro_targets.update(new_targets.keys())
        issue_names_requiring_events.update(new_targets.keys())
        targets_by_id.update(new_targets)
        print("Gathering retro stuff")
        print(f"{len(targets_by_id)} issues so far")

    projective_targets = set()
    if spec.projective_query:
        print("Gathering proj stuff")
        proj_epic_names = get_epics_and_their_tasks_by_id(jira, spec.projective_query, all_issues_by_name, parents_child_keymap)
        new_targets = export_jira_epic_chain_to_targets(proj_epic_names, all_issues_by_name, parents_child_keymap)
        projective_targets.update(new_targets.keys())
        targets_by_id.update(new_targets)
        print(f"{len(targets_by_id)} issues so far")

    all_events = []
    for name in issue_names_requiring_events:
        all_events.extend(get_task_events(all_issues_by_name[name], spec.cutoff_date))

    apply_some_events_into_issues(targets_by_id, all_events)
    save_exported_jira_tasks(targets_by_id, retro_targets, retro_target_class)
    save_exported_jira_tasks(targets_by_id, projective_targets, proj_target_class)

    storer = event_manager_class()
    for e in all_events:
        storer.add_event(e)
    storer.save()
    print(f"Got about {len(all_events)} events")


def do_stuff(spec):
    import_targets_and_events(
        spec, simpledata.RetroTarget, simpledata.ProjTarget, simpledata.EventManager)
