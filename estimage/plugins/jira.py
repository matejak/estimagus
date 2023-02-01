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
    "VERIFIED": target.State.done,
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
    subtasks = jira.search_issues(f'"Epic Link" = {epic.key}', expand="changelog")
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
        subtask = jira.issue(subtask.key, expand="changelog")
        known_issues_by_id[subtask.key] = subtask
        recursively_identify_task_subtasks(jira, subtask, known_issues_by_id, parents_child_keymap)


def get_epics_and_tasks_by_id(jira, epics_query, all_items_by_name, parents_child_keymap):
    epics = jira.search_issues(f"type = epic AND {epics_query}", expand="changelog")

    new_epics_names = set()
    for epic in epics:
        new_epics_names.add(epic.key)
        if epic.key in all_items_by_name:
            continue
        all_items_by_name[epic.key] = epic
        identify_epic_subtasks(jira, epic, all_items_by_name, parents_child_keymap)
    return new_epics_names


def merge_jira_item_without_children(result_class, item, all_items_by_id, parents_child_keymap):
    STORY_POINTS = "customfield_12310243"
    EPIC_LINK = "customfield_12311140"
    CONTRIBUTORS = "customfield_12315950"
    COMMITMENT = "customfield_12317404"

    result = result_class()
    result.name = item.key
    result.title = item.get_field("summary") or ""
    result.description = item.get_field("description") or ""
    result.point_cost = float(item.get_field(STORY_POINTS) or 0)
    result.state = JIRA_STATUS_TO_STATE.get(str(item.get_field("status")), target.State.unknown)
    result.tags = {f"label:{value}" for value in (item.get_field("labels") or [])}
    result.collaborators = []

    try:
        result.collaborators += [c.key for c in item.get_field(CONTRIBUTORS) or []]
    except AttributeError:
        pass

    try:
        if commitment_item := item.get_field(COMMITMENT):
            result.tags.add(f"commitment:{commitment_item.value.lower()}")
    except AttributeError:
        pass

    return result


def inherit_attributes(parent, child):
    parent.add_element(child)


def resolve_inheritance_of_attributes(name, all_items_by_id, parents_child_keymap):
    item = all_items_by_id[name]
    child_names = parents_child_keymap.get(item.name, [])
    for child_name in child_names:
        child = all_items_by_id[child_name]
        inherit_attributes(item, child)
        resolve_inheritance_of_attributes(child_name, all_items_by_id, parents_child_keymap)


def export_jira_epic_chain_to_targets(root_names, all_issues_by_id, parents_child_keymap, target_class):
    all_targets_by_id = dict()
    for iid, issue in all_issues_by_id.items():
        all_targets_by_id[iid] = merge_jira_item_without_children(target_class, issue, all_issues_by_id, parents_child_keymap)
    for root_name in root_names:
        resolve_inheritance_of_attributes(root_name, all_targets_by_id, parents_child_keymap)
    return all_targets_by_id


def save_exported_jira_tasks(targets_by_id):
    for t in targets_by_id.values():
        t.save_metadata()
        t.save_point_cost()
        t.save_time_cost()


def jira_datetime_to_datetime(jira_datetime):
    date_str = jira_datetime.split("+")[0]
    return datetime.datetime.fromisoformat(date_str)


def import_event(event, date, related_task_name):
    STORY_POINTS = "customfield_12310243"
    EPIC_LINK = "customfield_12311140"

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

    return evt


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
    if spec.retrospective_query:
        retro_epic_names = get_epics_and_tasks_by_id(jira, spec.retrospective_query, all_issues_by_name, parents_child_keymap)
        new_targets = export_jira_epic_chain_to_targets(retro_epic_names, all_issues_by_name, parents_child_keymap, retro_target_class)
        issue_names_requiring_events.update(new_targets.keys())
        targets_by_id.update(new_targets)
        print("Gathering retro stuff")
        print(f"{len(targets_by_id)} issues so far")

    if spec.projective_query:
        print("Gathering proj stuff")
        proj_epic_names = get_epics_and_tasks_by_id(jira, spec.projective_query, all_issues_by_name, parents_child_keymap)
        new_targets = export_jira_epic_chain_to_targets(retro_epic_names, all_issues_by_name, parents_child_keymap, proj_target_class)
        targets_by_id.update(new_targets)
        print(f"{len(targets_by_id)} issues so far")

    save_exported_jira_tasks(targets_by_id)

    all_events = []
    for name in issue_names_requiring_events:
        all_events.extend(get_task_events(all_issues_by_name[name], spec.cutoff_date))
    storer = event_manager_class()
    for e in all_events:
        storer.add_event(e)
    storer.save()
    print(f"Got about {len(all_events)} events")


def do_stuff(spec):
    import_targets_and_events(
        spec, simpledata.RetroTarget, simpledata.ProjTarget, simpledata.EventManager)
