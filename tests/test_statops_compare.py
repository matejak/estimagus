import estimage.statops.compare as tm
import estimage.data as data

import pytest


def integ_approx(x):
    return pytest.approx(x, abs=tm.INTEGRATION_PRECISION)


def test_compare_trivial():
    assert tm.is_lower([0], [1], [1]) == 0.5
    degenerate_estimate = data.Estimate(1, 0)
    assert tm.estimate_is_lower(degenerate_estimate, degenerate_estimate) == 0.5


def test_compare_equal():
    assert tm.is_lower([0, 1], [1, 1], [1, 1]) == 0.5
    assert tm.is_lower([0, 1, 2], [1, 1, 1], [1, 1, 1]) == 0.5
    assert tm.is_lower([0, 1, 2, 3], [1, 1, 1, 1], [1, 1, 1, 1]) == 0.5
    assert tm.is_lower([0, 1, 2], [0, 1, 0], [1, 1, 1]) == 0.5
    simple_estimate = data.Estimate.from_triple(1, 0, 2)
    assert tm.estimate_is_lower(simple_estimate, simple_estimate) == 0.5
    concrete_estimate = data.Estimate.from_triple(2, 1, 3)
    assert tm.estimate_is_lower(concrete_estimate, concrete_estimate) == 0.5


def test_compare_clear():
    assert tm.is_lower([0, 1], [0, 1], [1, 0]) == 0
    assert tm.is_lower([0, 1], [1, 0], [0, 1]) == 1
    assert tm.estimate_is_lower(data.Estimate(1, 0), data.Estimate(0, 0)) == 0
    assert tm.estimate_is_lower(data.Estimate(0, 0), data.Estimate(1, 0)) == 1
    assert tm.is_lower([0, 1, 2, 3], [1, 1, 0, 0], [0, 0, 1, 1]) == 1
    assert tm.is_lower([0, 1, 2, 3], [0, 0, 1, 1], [1, 1, 0, 0]) == 0
    low_estimate = data.Estimate.from_triple(1, 0, 3)
    high_estimate = data.Estimate.from_triple(4, 3, 6)
    assert tm.estimate_is_lower(low_estimate, high_estimate) == integ_approx(1)
    assert tm.estimate_is_lower(high_estimate, low_estimate) == integ_approx(0)


def test_compare_overlapping():
    low_estimate = data.Estimate.from_triple(1, 0, 3)
    test_estimate = data.Estimate(1, 0)
    assert 0 < tm.estimate_is_lower(low_estimate, test_estimate) < 0.5
    assert 0.5 < tm.estimate_is_lower(test_estimate, low_estimate) < 1
    almost_low_estimate = data.Estimate.from_triple(1.1, 0.1, 3.1)
    assert 0.5 < tm.estimate_is_lower(low_estimate, almost_low_estimate) < 0.6
    low_end_estimate = data.Estimate.from_triple(0.5, 0, 1)
    assert 0.1 < tm.estimate_is_lower(low_estimate, low_end_estimate) < 0.2
    assert 0.8 < tm.estimate_is_lower(low_end_estimate, low_estimate) < 0.9


def test_compare_weighted():
    assert 0.99 < tm.is_lower([0, 1, 2, 3], [1, 1, 0, 0], [0, 0.01, 1, 1]) < 1

# TODO: Comparison of estimates
# TODO: %-complete
