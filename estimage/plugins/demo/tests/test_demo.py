import datetime

import pytest

from estimage import plugins, data, PluginResolver, persistence
import estimage.plugins.demo as tm

from tests.test_card import base_card_load_save, fill_card_instance_with_stuff, assert_cards_are_equal
from tests.test_inidata import temp_filename


@pytest.fixture
def card_io(resolver):
    ret = persistence.get_persistence(data.BaseCard, "memory")
    ret.forget_all()
    yield ret
    ret.forget_all()


@pytest.fixture
def event_io(resolver):
    ret = persistence.get_persistence(data.Event, "memory")
    ret.forget_all()
    yield ret
    ret.forget_all()


@pytest.fixture
def storage_io(resolver):
    ret = persistence.get_persistence(resolver.get_final_class("Storage"), "memory")
    ret.forget_all()
    yield ret
    ret.forget_all()


@pytest.fixture
def resolver():
    ret = PluginResolver()
    ret.add_known_extendable_classes()
    ret.resolve_extension(tm)
    return ret


@pytest.fixture
def demo_definition(card_io, storage_io, event_io):
    statuses = data.Statuses()
    someday = datetime.datetime(2024, 2, 3)
    kwargs = dict(
        start_date=someday,
        card_io=card_io,
        plugin_io=storage_io,
        event_io=event_io,
        statuses=statuses,
    )
    return kwargs


@pytest.fixture
def some_cards(card_io):
    a = data.BaseCard("a")
    a.status = "todo"
    a.title = "Proud A"
    b = data.BaseCard("b")
    b.status = "in_progress"
    c = data.BaseCard("c")
    d = data.BaseCard("d")
    d.status = "done"
    d.title = "Proud D"
    cards = [a, b, c, d]
    card_io.bulk_save_metadata(cards)


@pytest.fixture
def doer(some_cards, demo_definition):
    ret = tm.Demo(** demo_definition)
    return ret


@pytest.fixture
def empty_doer(demo_definition):
    ret = tm.Demo(** demo_definition)
    return ret


def test_select_tasks_not_finished(doer):
    assert len(doer.cards_by_id) == 4
    assert len(doer.get_not_finished_cards()) == 2
    choices = doer.get_sensible_choices()
    assert len(choices) == 2


def test_start(doer):
    doer.start_if_on_start()
    assert len(doer.get_not_finished_cards()) == 4
    choices = doer.get_sensible_choices()
    assert len(choices) == 4


def test_empty_doer(empty_doer):
    assert len(empty_doer.cards_by_id) == 0
    choices = empty_doer.get_sensible_choices()
    assert len(choices) == 1
