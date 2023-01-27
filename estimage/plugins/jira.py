import dataclasses
import datetime
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


def get_epics_and_tasks_by_id(jira, epics_query):
    issues = jira.search_issues(f"type = epic AND {epics_query}")

    all_epics = dict()
    all_subtasks = dict()
    for i in issues:
        all_epics[i.key] = i
        subtasks = jira.search_issues(f'"Epic Link" = {i.id}', expand="changelog")
        for t in subtasks:
            all_subtasks[t.key] = t
    return all_epics, all_subtasks


def merge_jira_item(jira, result_class, item, exported_items_by_name, new_subtasks_by_id):
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

    if (epic_id := item.get_field(EPIC_LINK)) and epic_id in exported_items_by_name:
        result.tags.update(exported_items_by_name[epic_id].tags)
        exported_items_by_name[epic_id].add_element(result)

    exported_items_by_name[item.key] = result

    if subtasks := item.get_field("subtasks"):
        for subtask in subtasks:
            subtask = jira.issue(subtask.key, expand="changelog")
            new_subtasks_by_id[subtask.key] = subtask
            subtask_item = merge_jira_item(jira, result_class, subtask, exported_items_by_name, new_subtasks_by_id)
            subtask_item.tags.update(result.tags)
            exported_items_by_name[subtask.key] = subtask_item
            exported_items_by_name[item.key].add_element(subtask_item)

    return result


def export_jira_tasks_to_targets(jira, epics, tasks, target_class: target.BaseTarget, new_subtasks_by_id):
    targets_by_id = dict()
    for e in epics.values():
        merge_jira_item(jira, target_class, e, targets_by_id, new_subtasks_by_id)

    for t in tasks.values():
        merge_jira_item(jira, target_class, t, targets_by_id, new_subtasks_by_id)

    return targets_by_id


def save_exported_jira_tasks(targets_by_id):
    for t in targets_by_id.values():
        t.save_metadata()
        t.save_point_cost()
        t.save_time_cost()


def get_task_events(task, cutoff_date, sprint_epics=frozenset()):
    cutoff_datetime = None
    if cutoff_date:
        cutoff_datetime = datetime.datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day)
    STORY_POINTS = "customfield_12310243"
    EPIC_LINK = "customfield_12311140"

    events = []
    for history in task.changelog.histories:
        date_str = history.created
        date_str = date_str.split("+")[0]
        date = datetime.datetime.fromisoformat(date_str)

        if cutoff_datetime and date < cutoff_datetime:
            continue

        for event in history.items:

            field_name = event.field
            former_value = event.fromString
            new_value = event.toString

            if field_name == "status":
                evt = evts.Event(task.key, "state", date)
                evt.value_before = JIRA_STATUS_TO_STATE.get(former_value, target.State.unknown)
                evt.value_after = JIRA_STATUS_TO_STATE.get(new_value, target.State.unknown)
                evt.msg = f"Status changed from '{former_value}' to '{new_value}'"
            elif field_name == STORY_POINTS:
                evt = evts.Event(task.key, "points", date)
                evt.value_before = float(former_value or 0)
                evt.value_after = float(new_value or 0)
                evt.msg = f"Points changed from {former_value} to {new_value}"
            elif field_name == EPIC_LINK:
                evt = evts.Event(task.key, "project", date)
                evt.value_before = int(former_value in sprint_epics)
                evt.value_after = int(new_value in sprint_epics)
                evt.msg = f"Got assigned epic {new_value}"
            else:
                continue

            events.append(evt)

    return events


def import_targets_and_events(spec, retro_target_class, proj_target_class, event_manager_class):
    targets_by_id = dict()
    all_tasks = dict()
    new_subtasks_by_id = dict()

    jira = JIRA(spec.server_url, token_auth=spec.token)
    if spec.retrospective_query:
        print("Gathering retro stuff")
        retro_epics, retro_tasks = get_epics_and_tasks_by_id(jira, spec.retrospective_query)
        new_targets = export_jira_tasks_to_targets(jira, retro_epics, retro_tasks, retro_target_class, new_subtasks_by_id)
        targets_by_id.update(new_targets)
        all_tasks.update(retro_tasks)

    if spec.projective_query:
        print("Gathering proj stuff")
        proj_epics, proj_tasks = get_epics_and_tasks_by_id(jira, spec.projective_query)
        new_targets = export_jira_tasks_to_targets(jira, proj_epics, proj_tasks, proj_target_class, new_subtasks_by_id)
        targets_by_id.update(new_targets)
        all_tasks.update(proj_tasks)

    print(f"Got about {len(targets_by_id)} tasks")
    save_exported_jira_tasks(targets_by_id)

    all_events = []
    all_tasks.update(new_subtasks_by_id)
    for t in all_tasks.values():
        all_events.extend(get_task_events(t, spec.cutoff_date))
    storer = event_manager_class()
    for e in all_events:
        storer.add_event(e)
    storer.save()
    print(f"Got about {len(all_events)} events")


def do_stuff(spec):
    import_targets_and_events(
        spec, simpledata.RetroTarget, simpledata.ProjTarget, simpledata.EventManager)
