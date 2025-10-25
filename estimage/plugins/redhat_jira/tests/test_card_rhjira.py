import pytest

from estimage import plugins, PluginResolver, persistence
import estimage.plugins.redhat_jira as tm

from tests.test_card import base_card_load_save, fill_card_instance_with_stuff, assert_cards_are_equal, TesCardIO
from tests.test_inidata import temp_filename, get_file_based_io


@pytest.fixture
def new_class():
    resolver = PluginResolver()
    resolver.add_known_extendable_classes()
    assert "BaseCard" in resolver.class_dict
    resolver.resolve_extension(tm, dict(BaseCard="BaseCardWithStatus"))
    cls = resolver.class_dict["BaseCard"]
    return cls


@pytest.fixture(params=("ini", "memory", "toml"))
def card_io(request, temp_filename, new_class):
    io = get_file_based_io(new_class, request.param, temp_filename)
    yield io
    io.forget_all()


def plugin_fill(card):
    fill_card_instance_with_stuff(card)

    card.status_summary = "Lorem Ipsum and So On"


def plugin_test(lhs, rhs):
    assert_cards_are_equal(lhs, rhs)
    assert lhs.status_summary == rhs.status_summary
    assert lhs.status_summary_time == rhs.status_summary_time


def test_card_load_and_save_values(new_class, card_io):
    base_card_load_save(card_io, new_class, plugin_fill, plugin_test)
