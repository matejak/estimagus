import datetime

import jinja2

import history as hist


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
def get_tasks():
    from jira import JIRA
    TOKEN = con.token

    jira = JIRA(con.server_url, token_auth=TOKEN)
    issues = jira.search_issues(con.query)
    all_subtasks = dict()
    for i in issues:
        subtasks = jira.search_issues(f'"Epic Link" = {i.id}', expand="changelog")
        for t in subtasks:
            if not ours(t):
                continue
            all_subtasks[t.key] = t
    return all_subtasks


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
                evt = hist.Event(date)
                evt.value = JIRA_STATUS_TO_STATE[former_value]
                result["status"].append(evt)
            elif field_name == STORY_POINTS:
                evt = hist.Event(date)
                evt.value = float(former_value or 0)
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

        events = get_events(task, start)
        task_repre.status_timeline.process_events(events["status"])
        task_repre.points_timeline.process_events(events["points"])
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


TEMPLATE_HTML = """
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


def generate_html(tasks):
    start = datetime.datetime(2022, 10, 1)
    end = datetime.datetime(2022, 12, 1)

    today = datetime.datetime.today()

    aggregation = hist.Aggregation()

    sorted_tasks = [tasks[key] for key in sorted(tasks.keys())]


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
    template = environment.from_string(TEMPLATE_HTML)
    content = template.render(data=data)
    with open("index.html", "w") as f:
        f.write(content)

