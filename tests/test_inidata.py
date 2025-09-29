import tempfile
import os
import datetime

import pytest

import estimage.inidata as tm
from estimage import persistence
from estimage.persistence.card import ini
import estimage.data as data
from tests.test_events import early_event, less_early_event


@pytest.fixture
def temp_filename():
    fd, filename = tempfile.mkstemp()
    os.close(fd)

    yield filename

    os.remove(filename)


@pytest.fixture
def inifile_temploc(temp_filename):
    class TmpIniCardIO:
        CONFIG_FILENAME = temp_filename

    yield TmpIniCardIO


@pytest.fixture
def cardio_inifile_cls(inifile_temploc):
    class FullBlownIO(inifile_temploc, ini.IniCardIO):
        pass

    yield FullBlownIO


@pytest.fixture
def eventmgr_relevant_io(temp_filename):
    class TmpIniEventMgr(persistence.event.ini.IniEventsIO):
        CONFIG_FILENAME = temp_filename

    yield TmpIniEventMgr


@pytest.fixture
def appdata_inifile(temp_filename):
    class TmpIniAppdata(tm.IniAppdata):
        CONFIG_FILENAME = temp_filename

    yield TmpIniAppdata


def test_eventmgr_storage(eventmgr_relevant_io, early_event, less_early_event):
    mgr_one = data.EventManager()
    mgr_one.add_event(early_event)
    mgr_one.save(eventmgr_relevant_io)

    mgr_two = data.EventManager()
    mgr_two.load(eventmgr_relevant_io)
    assert mgr_two.get_chronological_task_events_by_type(early_event.task_name) == {None: [early_event]}

    less_early_event.value_before = "rano"
    less_early_event.value_after = "vecer"
    less_early_event.task_name = "den"
    mgr_one.add_event(less_early_event)

    mgr_one.save(eventmgr_relevant_io)
    mgr_two = data.EventManager()
    mgr_two.load(eventmgr_relevant_io)

    assert mgr_two.get_chronological_task_events_by_type(
        less_early_event.task_name) == {None: [less_early_event]}

    less_early_event.task_name = early_event.task_name
    mgr_one.add_event(less_early_event)

    mgr_one.save(eventmgr_relevant_io)
    mgr_two = data.EventManager()
    mgr_two.load(eventmgr_relevant_io)

    assert mgr_two.get_chronological_task_events_by_type(early_event.task_name) == {None: [early_event, less_early_event]}


def test_eventmgr_storage_float(eventmgr_relevant_io, early_event):
    mgr_one = data.EventManager()
    early_event.value_after = 8.5
    early_event.value_before = 5.4
    early_event.quantity = "points"
    mgr_one.add_event(early_event)
    mgr_one.save(eventmgr_relevant_io)

    mgr_two = data.EventManager()
    mgr_two.load(eventmgr_relevant_io)
    assert mgr_two.get_chronological_task_events_by_type(early_event.task_name) == {"points": [early_event]}


def test_eventmgr_storage_state(eventmgr_relevant_io, early_event):
    mgr_one = data.EventManager()
    early_event.value_after = "abandoned"
    early_event.value_before = "in_progress"
    early_event.quantity = "state"
    mgr_one.add_event(early_event)
    mgr_one.save(eventmgr_relevant_io)

    mgr_two = data.EventManager()
    mgr_two.load(eventmgr_relevant_io)
    assert mgr_two.get_chronological_task_events_by_type(early_event.task_name) == {"state": [early_event]}


def test_appdata_storage(appdata_inifile):
    data = appdata_inifile()
    data.RETROSPECTIVE_PERIOD = [
        datetime.datetime(2001, 4, 1),
        datetime.datetime(2001, 6, 30),
    ]
    data.PROJECTIVE_QUARTER = "abcd"
    data.RETROSPECTIVE_QUARTER = "cd00"
    data.save()

    data2 = appdata_inifile.load()
    assert data2.RETROSPECTIVE_PERIOD == data.RETROSPECTIVE_PERIOD
    assert data2.PROJECTIVE_QUARTER == data.PROJECTIVE_QUARTER
    assert data2.RETROSPECTIVE_QUARTER == data.RETROSPECTIVE_QUARTER


def test_status_extraction():
    assert tm.get_canonical_status("bzzt") == "bzzt"
    assert tm.get_canonical_status("0") == "irrelevant"
    assert tm.get_canonical_status("2") == "todo"
    assert tm.get_canonical_status("10") == "irrelevant"
