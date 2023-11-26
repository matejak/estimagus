import datetime

import pytest

from estimage import plugins, data, PluginResolver, persistence
from estimage.data import BaseTarget
import estimage.plugins.demo as tm

from tests.test_target import base_target_load_save, fill_target_instance_with_stuff, assert_targets_are_equal
from tests.test_inidata import temp_filename, targetio_inifile_cls


@pytest.fixture
def loader():
    loader_and_saver = (
        persistence.LOADERS[BaseTarget]["memory"],
        persistence.SAVERS[BaseTarget]["memory"])
    ret = type("loader", loader_and_saver, dict())
    ret.forget_all()
    yield ret
    ret.forget_all()


@pytest.fixture
def some_targets(loader):
    a = BaseTarget("a")
    a.state = data.State.todo
    a.title = "Proud A"
    b = BaseTarget("b")
    b.state = data.State.in_progress
    c = BaseTarget("c")
    d = BaseTarget("d")
    d.state = data.State.done
    d.title = "Proud D"
    targets = [a, b, c, d]
    loader.bulk_save_metadata(targets)


@pytest.fixture
def doer(some_targets, loader):
    someday = datetime.datetime(2024, 2, 3)
    ret = tm.Demo(loader, someday)
    return ret


@pytest.fixture
def empty_doer(loader):
    someday = datetime.datetime(2024, 2, 3)
    ret = tm.Demo(loader, someday)
    return ret


def test_select_tasks_not_finished(doer):
    assert len(doer.targets_by_id) == 4
    assert len(doer.get_not_finished_targets()) == 2
    choices = doer.get_sensible_choices()
    assert len(choices) == 2


def test_start(doer):
    doer.start_if_on_start()
    assert len(doer.get_not_finished_targets()) == 4
    choices = doer.get_sensible_choices()
    assert len(choices) == 4


def test_empty_doer(empty_doer):
    assert len(empty_doer.targets_by_id) == 0
    choices = empty_doer.get_sensible_choices()
    assert len(choices) == 1
