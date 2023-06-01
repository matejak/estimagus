import pytest

from estimage import plugins, PluginResolver, persistence
from estimage.data import BaseTarget
import estimage.plugins.redhat_compliance as tm

from tests.test_target import base_target_load_save, fill_target_instance_with_stuff, assert_targets_are_equal
from tests.test_inidata import temp_filename, targetio_inifile_cls


@pytest.fixture(params=("ini",))
def target_io(request, targetio_inifile_cls):
    cls = tm.BaseTarget
    choices = dict(
        ini=targetio_inifile_cls,
    )
    backend = request.param
    appropriate_io = type(
            "test_io",
            (choices[backend], persistence.LOADERS[cls][backend], persistence.SAVERS[cls][backend]),
            dict())
    return appropriate_io


def plugin_fill(t):
    fill_target_instance_with_stuff(t)

    t.status_summary = "Lorem Ipsum and So On"
    # t.status_summary_time = datetime.datetime(1918, 8, 3)


def plugin_test(lhs, rhs):
    assert_targets_are_equal(lhs, rhs)
    assert lhs.status_summary == rhs.status_summary
    assert lhs.status_summary_time == rhs.status_summary_time


def test_target_load_and_save_values(target_io):
    resolver = PluginResolver()
    resolver.add_known_overridable_classes()
    assert "BaseTarget" in resolver.class_dict
    resolver.resolve_overrides(tm)
    cls = resolver.class_dict["BaseTarget"]
    base_target_load_save(target_io, cls, plugin_fill, plugin_test)
