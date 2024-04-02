import datetime
import random

import estimage.simpledata as sd
from estimage.persistence.card import ini
from estimage import data


def create_task(name, points, status="todo"):
    t = data.BaseCard(name)
    t.point_cost = points
    t.assignee = "marty"
    if random.random() > 0.5:
        t.collaborators.append("andy")
    t.status = status
    t.title = f"Issue {name}"
    t.description = f"Description of Issue {name}"
    return t


def create_epic(name, children=None, status="in_progress"):
    t = data.BaseCard(name)
    t.name = name
    t.title = f"Epic {name}"
    t.assignee = "marty"
    t.description = f"Description of Epic {name}"
    t.status = status
    if children:
        t.children = children
        for c in children:
            c.parent = t
    return t


def create_projective_tasks_and_epics():
    real_saver = type("RealSaver", (sd.ProjCardIO, ini.IniCardSaver), dict())
    t1 = create_task("future-one", 1)
    t2 = create_task("future-two", 2)
    t3 = create_task("future-three", 3)
    e1 = create_epic("future-first", children=[t1, t2])
    e3 = create_epic("future-deep", children=[t3])
    e4 = create_epic("future-shallow", children=[e3])
    real_saver.bulk_save_metadata([t1, t2, t3, e1, e3, e4])


def create_status_events_for_task(task_name, end_status, period_interval):
    status_low_bound = 2
    statuses = data.Statuses().statuses[status_low_bound:]
    period_length = period_interval[1] - period_interval[0]
    dates = sorted([random.random() * period_length + period_interval[0] for _ in statuses])
    events = []
    before = data.Statuses().statuses[status_low_bound - 1]
    for status, when in zip(statuses, dates):
        event = data.Event(task_name, "state", when)
        event.value_before = before.name
        event.value_after = status.name
        before = status
        events.append(event)
    return events


def dispatch_events_for_task(manager, task_name, end_status, period):
    events = create_status_events_for_task(task_name, end_status, period)
    for e in events:
        manager.add_event(e)


def create_retrospective_events():
    manager = sd.EventManager()
    period = list(sd.AppData()._get_default_retrospective_period())
    period[1] = datetime.datetime.today()
    dispatch_events_for_task(manager, "past-one", "done", period)
    dispatch_events_for_task(manager, "past-two", "done", period)
    dispatch_events_for_task(manager, "past-three", "in_progress", period)
    dispatch_events_for_task(manager, "past-four", "done", period)
    manager.save()


def create_retrospective_tasks_and_epics():
    real_saver = type("RealSaver", (sd.RetroCardIO, ini.IniCardSaver), dict())

    t1 = create_task("past-one", 1, "done")

    t2 = create_task("past-two", 2, "in_progress")
    t3 = create_task("past-three", 3, "done")
    e1 = create_epic("past-first", children=[t1, t2])
    e3 = create_epic("past-deep", children=[t3], status="done")
    e4 = create_epic("past-shallow", children=[e3], status="done")

    t4 = create_task("past-four", 5, "done")
    t5 = create_task("past-five", 4, "todo")
    e5 = create_epic("past-second", children=[t4, t5])
    real_saver.bulk_save_metadata([t1, t2, t3, t4, t5, e1, e3, e4, e5])


if __name__ == "__main__":
    create_projective_tasks_and_epics()
    create_retrospective_tasks_and_epics()
    create_retrospective_events()
