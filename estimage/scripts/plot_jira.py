import datetime
import collections

import jinja2

import estimage.history as hist
import estimage.inidata as inidata
from estimage.entities import target


import con


JIRA_STATUS_TO_STATE = {
    "Backlog": hist.State.todo,
    "New": hist.State.todo,
    "Done": hist.State.done,
    "Abandoned": hist.State.abandoned,
    "Closed": hist.State.abandoned,
    "In Progress": hist.State.in_progress,
    "Needs Peer Review": hist.State.review,
    "To Do": hist.State.todo,
}


def ours(task):
    if not task.key.startswith("OPENSCAP"):
        return False
    return True


STORY_POINTS = "customfield_12310243"
EPIC_LINK = "customfield_12311140"


def get_tasks():
    from jira import JIRA
    TOKEN = con.token

    jira = JIRA(con.server_url, token_auth=TOKEN)
    issues = jira.search_issues(con.query)
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


def export_jira_tasks_to_targets(epics, tasks, target_class: target.BaseTarget):
    targets_by_id = dict()
    for e in epics:
        target = target_class()
        target.name = e.key
        target.title = e.get_field("summary")
        targets_by_id[e.key] = target

    for t in tasks:
        target = target_class()
        target.name = t.key
        target.title = t.get_field("summary")
        targets_by_id[t.key] = target
        target.point_cost = float(t.get_field(STORY_POINTS) or 0)

        epic_id = t.get_field(EPIC_LINK)
        targets_by_id[epic_id].add_element(target)

    return targets_by_id


def get_events(task, cutoff=None):
    result = dict(
        points=[],
        status=[],
    )
    for history in task.changelog.histories:
        date_str = history.created
        date_str = date_str.split("+")[0]
        date = datetime.datetime.fromisoformat(date_str)

        if cutoff and date < cutoff:
            continue

        for event in history.items:

            field_name = event.field
            former_value = event.fromString

            if field_name == "status":
                evt = hist.Event(task.key, date)
                evt.value = JIRA_STATUS_TO_STATE[former_value]
                evt.msg = f"Status changed from '{former_value}' to '{event.toString}'"
                result["status"].append(evt)
            elif field_name == STORY_POINTS:
                evt = hist.Event(task.key, date)
                evt.value = float(former_value or 0)
                evt.msg = f"Points changed from {former_value} to {event.toString}"
                result["points"].append(evt)

    return result


def our_plot(tasks):
    start = datetime.datetime(2022, 10, 1)
    end = datetime.datetime(2022, 12, 1)

    today = datetime.datetime.today()

    aggregation = hist.Aggregation()

    sorted_tasks = [tasks[key] for key in sorted(tasks.keys())]

    for task in sorted_tasks:
        task_repre = hist.Repre(start, end)
        points = float(task.get_field(STORY_POINTS) or 0)
        status = JIRA_STATUS_TO_STATE[str(task.get_field("status"))]
        task_repre.update(today, points=points, status=status)
        task_repre.fill_history_from(today)

        events_lists = get_events(task, start)
        task_repre.status_timeline.process_events(events_lists["status"])
        task_repre.points_timeline.process_events(events_lists["points"])
        if points:
            print(f"{points} {task.key} - {task.get_field('summary')}")

        aggregation.add_repre(task_repre)

    plotter = hist.MPLPlot(aggregation)
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
    start = datetime.datetime(2022, 10, 1)
    end = datetime.datetime(2022, 12, 1)

    today = datetime.datetime.today()

    aggregation = hist.Aggregation()

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
    with open("index.html", "w") as f:
        f.write(content)


def get_linear_events(task, cutoff=None):
    events_lists = get_events(task, cutoff)
    ret = []
    for e_list in events_lists.values():
        ret.extend(e_list)
    return ret


def generate_events_html(tasks_by_name):
    start = datetime.datetime(2022, 10, 1)
    end = datetime.datetime(2022, 12, 1)

    today = datetime.datetime.today()

    aggregation = hist.Aggregation()

    events = []
    for t in tasks_by_name.values():
        events.extend(get_linear_events(t, start))

    events_by_date = collections.defaultdict(list)
    for e in events:
        events_by_date[str(e.time.date().isoformat())].append(e)

    environment = jinja2.Environment()
    template = environment.from_string(EVENTS_TEMPLATE_HTML)
    content = template.render(events_by_date=events_by_date, sorted_dates=sorted(events_by_date.keys()))
    with open("index.html", "w") as f:
        f.write(content)

