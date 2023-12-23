import datetime

import pytest

from estimage import plugins, data, PluginResolver, persistence
from estimage.data import BaseCard
import estimage.plugins.demo as tm

from tests.test_card import base_card_load_save, fill_card_instance_with_stuff, assert_cards_are_equal
from tests.test_inidata import temp_filename, cardio_inifile_cls


@pytest.fixture
def loader():
    loader_and_saver = (
        persistence.LOADERS[BaseCard]["memory"],
        persistence.SAVERS[BaseCard]["memory"])
    ret = type("loader", loader_and_saver, dict())
    ret.forget_all()
    yield ret
    ret.forget_all()


@pytest.fixture
def some_cards(loader):
    a = BaseCard("a")
    a.status = data.STATUSES.get("todo")
    a.title = "Proud A"
    b = BaseCard("b")
    b.status = data.STATUSES.get("in_progress")
    c = BaseCard("c")
    d = BaseCard("d")
    d.status = data.STATUSES.get("done")
    d.title = "Proud D"
    cards = [a, b, c, d]
    loader.bulk_save_metadata(cards)


@pytest.fixture
def doer(some_cards, loader):
    someday = datetime.datetime(2024, 2, 3)
    ret = tm.Demo(loader, someday)
    return ret


@pytest.fixture
def empty_doer(loader):
    someday = datetime.datetime(2024, 2, 3)
    ret = tm.Demo(loader, someday)
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
