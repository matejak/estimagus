import pytest

from estimage import plugins, PluginResolver, persistence
import estimage.plugins.redhat_compliance as tm

from tests.test_card import base_card_load_save, fill_card_instance_with_stuff, assert_cards_are_equal
from tests.test_inidata import temp_filename, cardio_inifile_cls


@pytest.fixture(params=("ini",))
def card_io(request, cardio_inifile_cls):
    cls = tm.BaseCardWithStatus
    choices = dict(
        ini=cardio_inifile_cls,
    )
    backend = request.param
    appropriate_io = type(
            "test_io",
            (choices[backend], persistence.LOADERS[cls][backend], persistence.SAVERS[cls][backend]),
            dict())
    return appropriate_io


def plugin_fill(t):
    fill_card_instance_with_stuff(t)

    t.status_summary = "Lorem Ipsum and So On"


def plugin_test(lhs, rhs):
    assert_cards_are_equal(lhs, rhs)
    assert lhs.status_summary == rhs.status_summary
    assert lhs.status_summary_time == rhs.status_summary_time


def test_card_load_and_save_values(card_io):
    resolver = PluginResolver()
    resolver.add_known_extendable_classes()
    assert "BaseCard" in resolver.class_dict
    resolver.resolve_extension(tm)
    cls = resolver.class_dict["BaseCard"]
    base_card_load_save(card_io, cls, plugin_fill, plugin_test)
