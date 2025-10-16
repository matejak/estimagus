import pytest
import numpy as np

from estimage import data
from estimage import PluginResolver, persistence
from tests.test_inidata import temp_filename
from tests.test_card import get_file_based_io

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


@pytest.mark.parametrize("backend", ("ini", "memory", "toml"))
def test_card_io_children_of_correct_type(backend, temp_filename):
    parent = tm.IntervalCard("parent")
    child = tm.IntervalCard("child")
    parent.add_element(child)

    pr = PluginResolver()
    pr.add_known_extendable_classes()
    pr.resolve_extension(tm)

    card_io = get_file_based_io(tm.IntervalCard, backend, temp_filename)
    card_io.bulk_save_metadata([parent, child])

    loaded_parent = card_io.get_loaded_cards_by_id(tm.IntervalCard)["parent"]
    assert type(loaded_parent) is tm.IntervalCard
    assert type(loaded_parent) is type(loaded_parent.children[0])

    card_io.forget_all()


def test_estimation_properties():
    card = tm.IntervalCard("one")
    default_coef_of_var = tm.DEFAULT_CV
    inp = card.create_estim_input(1)
    est = data.Estimate.from_input(inp)
    assert est.sigma / est.expected == pytest.approx(default_coef_of_var)
    coef_of_var = 0.4
    with pytest.raises(ValueError, match="gamma"):
        inp = card.create_estim_input(1, coef_of_var)
    inp = card.create_estim_input(1, coef_of_var, 8)
    est = data.Estimate.from_input(inp)
    assert est.sigma / est.expected == pytest.approx(coef_of_var)
