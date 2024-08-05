import pytest

from estimage import data

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
