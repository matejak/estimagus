import tempfile
import os
import datetime

import pytest

import estimage.inidata as tm
import estimage.data as data
from test_history import early_event, less_early_event


@pytest.fixture
def temp_filename():
    fd, filename = tempfile.mkstemp()
    os.close(fd)

    yield filename

    os.remove(filename)


@pytest.fixture
def target_inifile(temp_filename):
    class TmpIniTarget(tm.IniTarget):
        CONFIG_FILENAME = temp_filename
        TIME_UNIT = "d"

    yield TmpIniTarget


@pytest.fixture
def eventmgr_inifile(temp_filename):
    class TmpIniEventMgr(tm.IniEvents):
        CONFIG_FILENAME = temp_filename

    yield TmpIniEventMgr


@pytest.fixture
def appdata_inifile(temp_filename):
    class TmpIniAppdata(tm.IniAppdata):
        CONFIG_FILENAME = temp_filename

    yield TmpIniAppdata


def test_require_name_for_saving(target_inifile):
    data = target_inifile()
    with pytest.raises(RuntimeError, match="blank"):
        data.save_metadata()


def test_load_non_existent(target_inifile):
    with pytest.raises(RuntimeError, match="something"):
        target_inifile.load_metadata("something")


@pytest.mark.dependency
def test_save_tree_load_same(target_inifile):
    data2 = target_inifile()
    data2.name = "second"

    data = target_inifile()
    data.name = "first"
    data.add_element(data2)
    data.save_metadata()

    loaded_data = target_inifile.load_metadata("first")
    assert loaded_data.dependents[0].name == "second"


@pytest.mark.dependency
def test_save_something_load_same(target_inifile):
    data = target_inifile()
    data.name = "name"
    data.title = "title"
    data.description = """A really\nnasty 'description' or "desc" %%boom!."""
    data.save_metadata()

    data2 = target_inifile.load_metadata("name")

    assert data.name == data2.name
    assert data.title == data2.title
    assert data.description == data2.description
    assert len(data2.dependents) == 0

    data.point_cost = 5
    assert data.point_cost != data2.point_cost
    data.save_point_cost()
    data2.load_point_cost()
    assert data.point_cost == data2.point_cost

    data.time_cost = 5
    assert data.time_cost != data2.time_cost
    data.save_time_cost()
    data2.load_time_cost()
    assert data.time_cost == data2.time_cost


@pytest.mark.dependency(depends=["test_save_something_load_same"])
def test_save_something2_load_same(target_inifile):
    data = target_inifile()
    data.name = "id"
    data.title = "titlung"
    data.save_metadata()

    data2 = target_inifile.load_metadata("id")

    assert data.name == data2.name
    assert data.title == data2.title


def test_eventmgr_storage(eventmgr_inifile, early_event, less_early_event):
    mgr_one = eventmgr_inifile()
    mgr_one.add_event(early_event)
    mgr_one.save()

    mgr_two = eventmgr_inifile.load()
    assert mgr_two.get_chronological_task_events_by_type(early_event.task_name) == {None: [early_event]}

    less_early_event.value_before = "rano"
    less_early_event.value_after = "vecer"
    less_early_event.task_name = "den"
    mgr_one.add_event(less_early_event)

    mgr_one.save()
    mgr_two = eventmgr_inifile.load()

    assert mgr_two.get_chronological_task_events_by_type(
        less_early_event.task_name) == {None: [less_early_event]}

    less_early_event.task_name = early_event.task_name
    mgr_one.add_event(less_early_event)

    mgr_one.save()
    mgr_two = eventmgr_inifile.load()

    assert mgr_two.get_chronological_task_events_by_type(early_event.task_name) == {None: [early_event, less_early_event]}


def test_eventmgr_storage_float(eventmgr_inifile, early_event):
    mgr_one = eventmgr_inifile()
    early_event.value_after = 8.5
    early_event.value_before = 5.4
    early_event.quantity = "points"
    mgr_one.add_event(early_event)
    mgr_one.save()

    mgr_two = eventmgr_inifile.load()
    assert mgr_two.get_chronological_task_events_by_type(early_event.task_name) == {"points": [early_event]}


def test_eventmgr_storage_state(eventmgr_inifile, early_event):
    mgr_one = eventmgr_inifile()
    early_event.value_after = data.State.abandoned
    early_event.value_before = data.State.in_progress
    early_event.quantity = "state"
    mgr_one.add_event(early_event)
    mgr_one.save()

    mgr_two = eventmgr_inifile.load()
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
