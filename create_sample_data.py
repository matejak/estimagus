import datetime
import random

import estimage.simpledata as sd
from estimage import data


def create_task(cls, name, points, state=data.State.todo):
    t = cls()
    t.name = name
    t.point_cost = points
    t.status = state
    t.title = f"Issue {name}"
    t.description = f"Description of Issue {name}"
    t.save_metadata()
    t.save_point_cost()
    return t


def create_projective_task(name, points):
    return create_task(sd.ProjCard, name, points)


def create_retrospective_task(name, points, state):
    return create_task(sd.RetroCard, name, points, state)


def create_epic(cls, name, children=None):
    t = cls()
    t.name = name
    t.title = f"Epic {name}"
    t.description = f"Description of Epic {name}"
    if children:
        t.dependents = children
    t.save_metadata()
    return t


def create_projective_epic(name, children=None):
    return create_epic(sd.ProjCard, name, children)


def create_retrospective_epic(name, children=None):
    return create_epic(sd.RetroCard, name, children)


def create_projective_tasks_and_epics():
    t1 = create_projective_task("future-one", 1)
    t2 = create_projective_task("future-two", 2)
    t3 = create_projective_task("future-three", 3)
    create_projective_epic("future-first", children=[t1, t2])
    e3 = create_projective_epic("future-deep", children=[t3])
    create_projective_epic("future-shallow", children=[e3])


def create_status_events_for_task(task_name, end_status, period_interval):
    status_low_bound = int(data.State.todo)
    period_length = period_interval[1] - period_interval[0]
    states = [data.State(code + 1) for code in range(status_low_bound, int(end_status))]
    dates = sorted([random.random() * period_length + period_interval[0] for _ in states])
    events = []
    before = data.State.todo
    for state, when in zip(states, dates):
        event = data.Event(task_name, "state", when)
        event.value_before = before
        event.value_after = state
        before = state
        events.append(event)
    return events


def dispatch_events_for_task(manager, task_name, end_status, period):
    events = create_status_events_for_task(task_name, end_status, period)
    for e in events:
        manager.add_event(e)


def create_retrospective_events():
    manager = sd.EventManager()
    period = (datetime.datetime(2022, 10, 1), datetime.datetime(2023, 1, 1))
    dispatch_events_for_task(manager, "past-one", data.State.done, period)
    dispatch_events_for_task(manager, "past-two", data.State.review, period)
    dispatch_events_for_task(manager, "past-three", data.State.in_progress, period)
    dispatch_events_for_task(manager, "past-four", data.State.done, period)
    manager.save()


def create_retrospective_tasks_and_epics():
    t1 = create_retrospective_task("past-one", 1, data.State.done)

    t2 = create_retrospective_task("past-two", 2, data.State.review)
    t3 = create_retrospective_task("past-three", 3, data.State.in_progress)
    create_retrospective_epic("past-first", children=[t1, t2])
    e3 = create_retrospective_epic("past-deep", children=[t3])
    create_retrospective_epic("past-shallow", children=[e3])

    t4 = create_retrospective_task("past-four", 5, data.State.done)
    t5 = create_retrospective_task("past-five", 4, data.State.todo)
    create_retrospective_epic("past-second", children=[t4, t5])


if __name__ == "__main__":
    create_projective_tasks_and_epics()
    create_retrospective_tasks_and_epics()
    create_retrospective_events()
