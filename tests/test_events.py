import datetime

import pytest

import estimage.data as data


ONE_DAY = datetime.timedelta(days=1)
PERIOD_START = datetime.datetime(2022, 10, 1)
LONG_PERIOD_END = datetime.datetime(2022, 10, 21)


@pytest.fixture
def early_event():
    early_date = datetime.datetime(2022, 10, 11, 12)
    early_event = data.Event("", None, early_date)
    early_event.value_before = "15"
    return early_event


@pytest.fixture
def less_early_event():
    less_early_date = datetime.datetime(2022, 10, 11, 13)
    less_early_event = data.Event("", None, less_early_date)
    less_early_event.value_before = "17"
    return less_early_event


@pytest.fixture
def late_event():
    time_late = datetime.datetime(2022, 10, 15)
    late_event = data.Event("", None, time_late)
    late_event.value_before = "10"
    late_event.value_after = "0"
    return late_event


def test_event_manager_trivial(early_event):
    mgr = data.EventManager()
    assert mgr.get_chronological_task_events_by_type(early_event.task_name) == dict()
    assert mgr.get_referenced_task_names() == set()

    mgr.add_event(early_event)
    assert mgr.get_chronological_task_events_by_type(early_event.task_name) == {None: [early_event]}
    assert mgr.get_referenced_task_names() == {early_event.task_name}

    assert mgr.get_chronological_task_events_by_type("x") == dict()


def test_event_manager(early_event, less_early_event):
    mgr = data.EventManager()
    mgr.add_event(less_early_event)
    mgr.add_event(early_event)
    events = mgr.get_chronological_task_events_by_type(early_event.task_name)
    assert events == {None: [early_event, less_early_event]}


def test_events_consistency_trivial():
    assert data.Event.consistent([])
