import app.inidata as tm

import configparser
import tempfile
import os

import pytest


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
