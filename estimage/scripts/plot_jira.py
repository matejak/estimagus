import datetime
import collections

import jinja2

import estimage.history as hist
import estimage.entities.event as evts
import estimage.inidata as inidata
import estimage.simpledata as webdata
from estimage.entities import target


import con


JIRA_STATUS_TO_STATE = {
    "Backlog": target.State.todo,
    "Refinement": target.State.todo,
    "New": target.State.todo,
    "Done": target.State.done,
    "Abandoned": target.State.abandoned,
    "Closed": target.State.abandoned,
    "In Progress": target.State.in_progress,
    "Needs Peer Review": target.State.review,
    "To Do": target.State.todo,
}


def ours(task):
    if not task.key.startswith("OPENSCAP"):
        return False
    return True


STORY_POINTS = "customfield_12310243"
EPIC_LINK = "customfield_12311140"


def get_tasks(query=con.query):
    from jira import JIRA
    TOKEN = con.token

    jira = JIRA(con.server_url, token_auth=TOKEN)
    issues = jira.search_issues(query)
    all_epics = dict()
    all_subtasks = dict()
    for i in issues:
        all_epics[i.key] = i
        subtasks = jira.search_issues(f'"Epic Link" = {i.id}', expand="changelog")
        for t in subtasks:
            if not ours(t):
                continue
            all_subtasks[t.key] = t
    return all_epics, all_subtasks


class HybridTarget(inidata.IniTarget):
    CONFIG_FILENAME = "jira-export.ini"


def export_jira_item(cls, item, exported_items_by_name):
    ret = cls()
    ret.name = item.key
    ret.title = item.get_field("summary") or ""
    ret.description = item.get_field("description") or ""
    ret.point_cost = float(item.get_field(STORY_POINTS) or 0)
    ret.state = JIRA_STATUS_TO_STATE.get(str(item.get_field("status")), target.State.unknown)
    ret.labels = item.get_field("labels") or []

    return ret


def export_jira_tasks_to_targets(epics, tasks, target_class: target.BaseTarget):
    targets_by_id = dict()
    for e in epics.values():
        targets_by_id[e.key] = export_jira_item(target_class, e, targets_by_id)

    for t in tasks.values():
        exported = export_jira_item(target_class, t, targets_by_id)
        targets_by_id[t.key] = exported
        if epic_id := t.get_field(EPIC_LINK):
            targets_by_id[epic_id].add_element(exported)

    return targets_by_id


def save_exported_jira_tasks(targets_by_id):
    for t in targets_by_id.values():
        t.save_metadata()
        t.save_point_cost()
        t.save_time_cost()


def export_projective_targets(query):
    epics, tasks = get_tasks(query)
    targets_by_id = export_jira_tasks_to_targets(epics, tasks, webdata.ProjTarget)
    save_exported_jira_tasks(targets_by_id)


def save_events(tasks, epics_names, event_manager_cls: type):
    storer = event_manager_cls()
    for t in tasks:
        events = get_events(t, sprint_epics=epics_names)
        for e in events:
            storer.add_event(e)
    storer.save()


def get_events(task, cutoff=None, sprint_epics=frozenset()):
    events = []
    for history in task.changelog.histories:
        date_str = history.created
        date_str = date_str.split("+")[0]
        date = datetime.datetime.fromisoformat(date_str)

        if cutoff and date < cutoff:
            continue

        for event in history.items:

            field_name = event.field
            former_value = event.fromString
            new_value = event.toString

            if field_name == "status":
                evt = evts.Event(task.key, "state", date)
                evt.value_before = JIRA_STATUS_TO_STATE[former_value]
                evt.value_after = JIRA_STATUS_TO_STATE[new_value]
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


def export_retrospective_targets(query):
    epics, tasks = get_tasks(query)
    targets_by_id = export_jira_tasks_to_targets(epics, tasks, webdata.RetroTarget)
    save_exported_jira_tasks(targets_by_id)

    save_events(tasks.values(), epics.keys(), webdata.EventManager)


def aggregate_tasks(tasks):
    start = datetime.datetime(2022, 10, 1)
    end = datetime.datetime(2022, 12, 23)

    today = datetime.datetime.today()
    last_day = min(end, today)

    aggregation = hist.Aggregation()

    sorted_tasks = [tasks[key] for key in sorted(tasks.keys())]
    all_events = []

    for task in sorted_tasks:
        task_repre = hist.Repre(start, end)
        task_repre.task_name = task.key
        points = float(task.get_field(STORY_POINTS) or 0)
        status = JIRA_STATUS_TO_STATE[str(task.get_field("status"))]

        all_events.append(evts.Event.last_state_measurement(task.key, last_day, status))
        all_events.append(evts.Event.last_points_measurement(task.key, last_day, points))

        all_events.extend(get_events(task, start))
        if points:
            print(f"{points} {task.key} - {task.get_field('summary')}")

        aggregation.add_repre(task_repre)

    aggregation.process_events(all_events)
    return aggregation


def our_plot(tasks):
    aggregation = aggregate_tasks(tasks)

    plotter = hist.MPLPointPlot(aggregation)
    plotter.plot_stuff()


def velocity_plot(tasks):
    aggregation = aggregate_tasks(tasks)
    today = datetime.datetime.today()

    plotter = hist.MPLVelocityPlot(aggregation)
    plotter.plot_stuff(today)


class Task:
    def __init__(self, task_obj):
        self.points = float(task_obj.get_field(STORY_POINTS) or 0)
        self.title = task_obj.get_field('summary')
        self.name = task_obj.key
        self.status = str(task_obj.get_field("status"))


EVENTS_TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Events</title>
  </head>
  <body>
    <h1>Events summary</h1>
    <ul>
    {% for date in sorted_dates %}
    <li>
    {{ date }}
    <ul>
    {% for e in events_by_date[date] %}
    <li>
    <a href="https://issues.redhat.com/browse/{{ e.task_name }}">{{ e.task_name }}</a> &mdash; {{ e.msg }}
    </li>
    {% endfor %}
    </ul>
    </li>
    {% endfor %}
    </ul>
  </body>
</html>
"""


TASKS_TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Summary</title>
  </head>
  <body>
    <h1>Tasks summary</h1>
    Total points: {{ data.points }}
    <ul>
    {% for task in data.tasks %}
    <li>
    <a href="https://issues.redhat.com/browse/{{ task.name }}">{{ task.name }}</a> &mdash; {{ task.title }}: {{ task.points }}
    </li>
    {% endfor %}
    </ul>
  </body>
</html>
"""


def generate_tasks_html(tasks_by_name):
    sorted_tasks = [tasks_by_name[key] for key in sorted(tasks_by_name.keys())]

    tasks_with_points = []
    point_sum = 0
    for task_obj in sorted_tasks:
        task = Task(task_obj)
        if task.points:
            tasks_with_points.append(task)
            point_sum += task.points

    data = dict(
        points=point_sum,
        tasks=tasks_with_points,
    )

    environment = jinja2.Environment()
    template = environment.from_string(TASKS_TEMPLATE_HTML)
    content = template.render(data=data)
    with open("index.html", "w", encoding="utf8") as f:
        f.write(content)


def generate_events_html(tasks_by_name):
    start = datetime.datetime(2022, 10, 1)

    events = []
    for t in tasks_by_name.values():
        events.extend(get_events(t, start))

    events_by_date = collections.defaultdict(list)
    for e in events:
        events_by_date[str(e.time.date().isoformat())].append(e)

    environment = jinja2.Environment()
    template = environment.from_string(EVENTS_TEMPLATE_HTML)
    content = template.render(events_by_date=events_by_date, sorted_dates=sorted(events_by_date.keys()))
    with open("index.html", "w", encoding="utf8") as f:
        f.write(content)
