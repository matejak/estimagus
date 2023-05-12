import tempfile
import os
import datetime

import pytest

import estimage.inidata as tm
import estimage.data as data
from test_events import early_event, less_early_event


@pytest.fixture
def temp_filename():
    fd, filename = tempfile.mkstemp()
    os.close(fd)

    yield filename

    os.remove(filename)


@pytest.fixture
def targetio_inifile_cls(temp_filename):
    class TmpIniTargetIO(tm.IniTargetIO):
        CONFIG_FILENAME = temp_filename

    yield TmpIniTargetIO


@pytest.fixture
def target_inifile(temp_filename):
    class TmpIniTarget(tm.IniTarget):
        CONFIG_FILENAME = temp_filename

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


def test_require_name_for_saving(targetio_inifile_cls):
    t = data.BaseTarget("")
    with pytest.raises(RuntimeError, match="blank"):
        t.save_metadata(targetio_inifile_cls)


def test_load_non_existent(targetio_inifile_cls):
    with pytest.raises(RuntimeError, match="something"):
        data.BaseTarget.load_metadata("something", targetio_inifile_cls)


@pytest.mark.dependency
def test_save_tree_load_same(targetio_inifile_cls):
    t2 = data.BaseTarget("second")
    t2.save_metadata(targetio_inifile_cls)

    t1 = data.BaseTarget("first")
    t1.add_element(t2)
    t1.save_metadata(targetio_inifile_cls)

    loaded_target = data.BaseTarget.load_metadata("first", targetio_inifile_cls)
    assert loaded_target.dependents[0].name == "second"


@pytest.mark.dependency
def test_save_something_load_same(targetio_inifile_cls):
    target = data.BaseTarget("name")
    target.title = "title"
    target.description = """A really\nnasty 'description' or "desc" %%boom!."""
    target.save_metadata(targetio_inifile_cls)

    data2 = data.BaseTarget.load_metadata("name", targetio_inifile_cls)

    assert target.name == data2.name
    assert target.title == data2.title
    assert target.description == data2.description
    assert len(data2.dependents) == 0

    target.point_cost = 5
    assert target.point_cost != data2.point_cost
    target.save_metadata(targetio_inifile_cls)
    data2 = data2.load_metadata("name", targetio_inifile_cls)
    assert target.point_cost == data2.point_cost


@pytest.mark.dependency(depends=["test_save_something_load_same"])
def test_save_something2_load_same(targetio_inifile_cls):
    target = data.BaseTarget("id")
    target.title = "titlung"
    target.save_metadata(targetio_inifile_cls)

    data2 = data.BaseTarget.load_metadata("id", targetio_inifile_cls)

    assert target.name == data2.name
    assert target.title == data2.title


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
