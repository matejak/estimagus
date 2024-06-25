import datetime
import os
import tempfile

import pytest

import estimage.entities.event as data
from estimage.persistence.event import memory, ini


def create_ini_events_io():
    fd, filename = tempfile.mkstemp()
    os.close(fd)

    class IniEventsIO(ini.IniEventsIO):
        CONFIG_FILENAME = filename

    return IniEventsIO


ONE_DAY = datetime.timedelta(days=1)
PERIOD_START = datetime.datetime(2022, 10, 1)
LONG_PERIOD_END = datetime.datetime(2022, 10, 21)
BACKENDS = dict(
    ini=create_ini_events_io(),
    memory=memory.MemoryEventsIO,
)


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


@pytest.fixture
def mgr():
    return data.EventManager()


def test_event_manager_trivial(mgr, early_event):
    assert mgr.get_chronological_task_events_by_type(early_event.task_name) == dict()
    assert mgr.get_referenced_task_names() == set()

    mgr.add_event(early_event)
    assert mgr.get_chronological_task_events_by_type(early_event.task_name) == {None: [early_event]}
    assert mgr.get_referenced_task_names() == {early_event.task_name}

    assert mgr.get_chronological_task_events_by_type("x") == dict()


def test_event_manager(mgr, early_event, less_early_event):
    mgr.add_event(less_early_event)
    mgr.add_event(early_event)
    events = mgr.get_chronological_task_events_by_type(early_event.task_name)
    assert events == {None: [early_event, less_early_event]}


def test_event_manager_erase(mgr, early_event, less_early_event):
    mgr.add_event(less_early_event)
    mgr.add_event(early_event)
    mgr.erase(memory.MemoryEventsIO)
    events = mgr.get_chronological_task_events_by_type(early_event.task_name)
    assert not events


@pytest.fixture(params=BACKENDS.keys())
def event_io(request):
    ret = BACKENDS[request.param]
    yield ret


def test_events_save(mgr, early_event, less_early_event, event_io):
    mgr.add_event(early_event)
    mgr.save(event_io)
    new_mgr = data.EventManager()
    new_mgr.load(event_io)
    task_names = new_mgr.get_referenced_task_names()
    assert len(task_names) == 1
    assert task_names.pop() == early_event.task_name

    newer_mgr = data.EventManager()
    mgr.erase(event_io)
    newer_mgr.load(event_io)
    task_names = newer_mgr.get_referenced_task_names()
    assert len(task_names) == 0


def test_events_consistency_trivial(early_event):
    assert data.Event.consistent([])

    assert data.Event.consistent([early_event])


def test_events_consistency_2tuples(early_event, less_early_event):
    early_event.value_after = 4
    less_early_event.value_before = 5

    assert not data.Event.consistent([early_event, less_early_event])

    early_event.value_before = 1
    early_event.value_after = 5
    less_early_event.value_before = 5
    less_early_event.value_after = 6
    assert data.Event.consistent([early_event, less_early_event])
    assert data.Event.consistent([less_early_event, early_event])


def test_events_consistency_3tuples(early_event, less_early_event, late_event):
    early_event.value_after = 2
    less_early_event.value_before = 2
    less_early_event.value_after = 3
    late_event.value_before = 4

    assert not data.Event.consistent([late_event, early_event, less_early_event])
