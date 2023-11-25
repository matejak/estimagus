import pytest

from estimage import plugins, data, PluginResolver, persistence
from estimage.data import BaseTarget
import estimage.plugins.demo as tm

from tests.test_target import base_target_load_save, fill_target_instance_with_stuff, assert_targets_are_equal
from tests.test_inidata import temp_filename, targetio_inifile_cls


@pytest.fixture
def some_targets():
    a = BaseTarget("a")
    a.state = data.State.todo
    b = BaseTarget("b")
    b.state = data.State.in_progress
    c = BaseTarget("c")
    d = BaseTarget("d")
    d.state = data.State.done
    return [a, b, c, d]


def test_select_tasks_not_finished(some_targets):
    doer = tm.Demo(some_targets, loader)
    assert not tm.get_not_finished_targets([])
    assert len(tm.get_not_finished_targets(some_targets)) == 2
