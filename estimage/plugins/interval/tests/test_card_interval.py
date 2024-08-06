import pytest

from estimage import data
from estimage import PluginResolver, persistence
from tests.test_inidata import cardio_inifile_cls, temp_filename
from tests.test_card import card_io

import estimage.plugins.interval as tm


def test_base_card():
    card = data.BaseCard("one")
    card.point_cost = 1

    point_tree = card.to_tree([card])
    assert point_tree.nominal_point_estimate.expected == pytest.approx(1, rel=0.01)
    assert point_tree.nominal_point_estimate.sigma == 0


def test_fuzzy_card():
    card = tm.IntervalCard("one")
    card.point_cost = 1

    fuzzy_tree = tm.IntervalCard.to_tree([card])
    assert fuzzy_tree.nominal_point_estimate.expected == pytest.approx(1, rel=0.01)
    assert fuzzy_tree.nominal_point_estimate.sigma > 0


def test_card_io_children_of_correct_type(temp_filename):
    parent = tm.IntervalCard("parent")
    child = tm.IntervalCard("child")
    parent.add_element(child)

    pr = PluginResolver()
    pr.add_known_extendable_classes()
    pr.resolve_extension(tm)
    interval_card = pr.class_dict["BaseCard"]
    ini_saver = persistence.SAVERS[interval_card]["ini"]
    ini_saver.CONFIG_FILENAME = temp_filename
    ini_loader = persistence.LOADERS[interval_card]["ini"]
    ini_loader.CONFIG_FILENAME = temp_filename

    ini_saver.bulk_save_metadata([parent, child])

    loaded_parent = ini_loader.get_loaded_cards_by_id(interval_card)["parent"]
    assert type(loaded_parent) is interval_card
    assert type(loaded_parent) is type(loaded_parent.children[0])


def test_estimation_properties():
    card = tm.IntervalCard("one")
    default_coef_of_var = 0.2643
    inp = card.create_estim_input(1)
    est = data.Estimate.from_input(inp)
    assert est.sigma / est.expected == pytest.approx(default_coef_of_var)
    coef_of_var = 0.7
    inp = card.create_estim_input(1, coef_of_var)
    est = data.Estimate.from_input(inp)
    assert est.sigma / est.expected == pytest.approx(coef_of_var)
