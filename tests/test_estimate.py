import math

import numpy as np

import estimage.entities.estimate as tm

import pytest


@pytest.fixture
def estiminput_1():
    return tm.EstimInput(1)


@pytest.fixture
def precise_estimate_1(estiminput_1):
    return tm.Estimate.from_input(estiminput_1)


@pytest.fixture
def estiminput_2():
    return tm.EstimInput(2)


@pytest.fixture
def precise_estimate_2(estiminput_2):
    return tm.Estimate.from_input(estiminput_2)


@pytest.fixture
def centered_estimate_345():
    return tm.Estimate.from_triple(4, 3, 5)


@pytest.fixture
def medium_estimate_346():
    return tm.Estimate.from_triple(4, 3, 6)


@pytest.fixture
def broad_estimate_246():
    return tm.Estimate.from_triple(4, 2, 6)


def test_estimate_invalid():
    with pytest.raises(ValueError, match="most likely"):
        tm.Estimate.from_triple(0, 1, 3)

    with pytest.raises(ValueError, match="most likely"):
        tm.Estimate.from_triple(4, 1, 3)

    with pytest.raises(ValueError, match="optimistic"):
        tm.Estimate.from_triple(2, 2.5, 3)

    with pytest.raises(ValueError, match="optimistic"):
        tm.Estimate.from_triple(2, 4, 3)

    with pytest.raises(ValueError, match="pessimistic"):
        tm.Estimate.from_triple(2, 1, 0)

    with pytest.raises(ValueError, match="pessimistic"):
        tm.Estimate.from_triple(2, 1, 1.5)


@pytest.mark.dependency
def test_estimates(precise_estimate_1, centered_estimate_345, medium_estimate_346):
    assert 6 > medium_estimate_346.expected > 4
    assert precise_estimate_1.expected == 1
    assert centered_estimate_345.expected == 4


def test_point_estimate_rvs():
    point_estimate = tm.Estimate.from_triple(1, 1, 1)
    assert np.all(point_estimate.pert_rvs(10)) == 1


@pytest.mark.dependency(depends=["test_estimates"])
def test_estimation_ranking_identity(medium_estimate_346):
    assert medium_estimate_346.rank_distance(medium_estimate_346) == 0


@pytest.mark.dependency(depends=["test_estimates"])
def test_estimation_ranking_reflexivity(centered_estimate_345, broad_estimate_246):
    assert (
        centered_estimate_345.rank_distance(broad_estimate_246)
        == broad_estimate_246.rank_distance(centered_estimate_345)
    )


@pytest.mark.dependency(depends=["test_estimates"])
def test_estimation_ranking_distance_of_precise_estimates(precise_estimate_1, precise_estimate_2):
    assert precise_estimate_1.rank_distance(precise_estimate_2) == float("inf")
    assert precise_estimate_2.rank_distance(precise_estimate_1) == float("inf")


@pytest.mark.dependency(depends=["test_estimates"])
def test_estimation_ranking_overlap(centered_estimate_345, medium_estimate_346, broad_estimate_246):
    distance_of_not_overlaping = centered_estimate_345.rank_distance(medium_estimate_346)
    distance_of_overlaping = broad_estimate_246.rank_distance(medium_estimate_346)
    assert distance_of_not_overlaping > distance_of_overlaping


def index_of_value_in_array_closest_to(arr, value):
    difference = np.abs(arr - value)
    return np.argmin(difference)


def pert_compute_expected_value(dom, values):
    contributions = dom * values
    imbalance = contributions.sum() / values.sum()
    return imbalance


def pert_test_estimate(est):
    pert = est.get_pert(100)
    assert pert.shape == (2, 100)

    pert_low_domain_boundary = pert[0][0]
    assert pert_low_domain_boundary <= est.source.optimistic
    pert_great_domain_boundary = pert[0][-1]
    assert pert_great_domain_boundary >= est.source.pessimistic

    surface_under_curve = pert[1].sum() * (pert[0][1] - pert[0][0])
    assert pytest.approx(surface_under_curve) == 1

    index_of_most_likely = np.argmax(pert[1])
    assert est.source.most_likely == pytest.approx(pert[0][index_of_most_likely], 0.05)

    deduced_expected_value = pert_compute_expected_value(pert[0], pert[1])
    assert pytest.approx(deduced_expected_value, 0.05) == est.expected


def _associativity_test(input_triples):
    estimates = [
        tm.Estimate.from_triple(* triple) for triple in input_triples
    ]
    onedir = estimates[0]
    for e in estimates[1:]:
        onedir = onedir + e

    otherdir = estimates[-1]
    for e in estimates[::-1][1:]:
        otherdir = e + otherdir

    assert onedir.expected == pytest.approx(otherdir.expected)
    assert onedir.sigma == pytest.approx(otherdir.sigma)


def test_estimate_associativity():
    _associativity_test((
        (2, 2, 2),
        (3, 3, 3),
        (5, 5, 5),
    ))
    _associativity_test((
        (2, 1, 3),
        (3, 1, 5),
        (5, 2, 8),
    ))
    _associativity_test((
        (1, 1, 3),
        (5, 1, 5),
        (5, 1, 13),
        (8, 2, 21),
        (2, 1, 3),
    ))


@pytest.mark.dependency(depends=["test_estimates"])
def test_pert():
    zero = tm.Estimate(0, 0)
    one = tm.Estimate(1, 0)
    zero_pert = zero.get_pert()
    index_of_max = np.argmax(zero_pert[1])
    assert zero_pert[0][index_of_max] == pytest.approx(0, abs=0.01)

    optimistic = 3
    most_likely = 4
    pessimistic = 6
    est = tm.Estimate.from_triple(most_likely, optimistic, pessimistic)
    with pytest.raises(ValueError, match="size"):
        est.get_pert(0)

    pert = est.get_pert(1)
    assert pert.shape == (2, 1)
    assert est.source.pessimistic >= pert[0][0] >= est.source.optimistic
    assert pert[1][0] == 1

    pert_test_estimate(est)
    est3 = tm.Estimate.from_triple(4, 3, 13)
    pert_test_estimate(est3)

    pert = est.get_pert(100)
    est2 = tm.Estimate.from_input(tm.EstimInput.from_pert_only(pert[0], pert[1]))
    assert est.expected == pytest.approx(est2.expected, 0.05)
    assert est.sigma == pytest.approx(est2.sigma, 0.05)

    dense_pert = est.get_pert(200)
    assert 0.99 < pert[1].sum() / (dense_pert[1].sum() * 0.5) < 1.01

    est_identical = est.compose_with(zero)
    assert est_identical.expected == est.expected
    assert est_identical.sigma == est.sigma

    est_shifted = est.compose_with(one)
    assert est_shifted.expected == est.expected + 1
    assert est_shifted.sigma == est.sigma

    est_composite = est.compose_with(est3)
    assert est3.expected + est.expected == pytest.approx(est_composite.expected, 0.05)
    assert math.sqrt(est3.sigma ** 2 + est.sigma ** 2) == pytest.approx(est_composite.sigma, 0.05)


def _test_triple(o, m, p):
    inp = tm.EstimInput(m)
    inp.optimistic = o
    inp.pessimistic = p

    norm_of_input = tm.EstimInput(0).distance_from(inp)

    estimate = tm.Estimate.from_input(inp)
    pert = estimate.get_pert(800)
    calculated_input = tm.EstimInput.from_pert_and_data(
        pert[0], pert[1], estimate.expected, estimate.sigma)
    calculated_estimate = tm.Estimate.from_input(calculated_input)

    assert pytest.approx(calculated_estimate.expected) == estimate.expected
    assert pytest.approx(calculated_estimate.sigma) == estimate.sigma

    assert pytest.approx(inp.distance_from(calculated_input), abs=norm_of_input * 2e-2) == 0


def test_lambda():
    most_likely = 2
    inp = tm.EstimInput(most_likely)
    inp.optimistic = 1
    inp.pessimistic = 4
    inp.LAMBDA = 2

    est = tm.Estimate.from_input(inp)
    low_lambda_expected = est.expected
    low_lambda_sigma = est.sigma
    o, p = tm.calculate_o_p_ext(most_likely, low_lambda_expected, low_lambda_sigma ** 2, est.LAMBDA)
    assert o == pytest.approx(1)
    assert p == pytest.approx(4)

    inp.LAMBDA = 8
    est = tm.Estimate.from_input(inp)
    hi_lambda_expected = est.expected
    hi_lambda_sigma = est.sigma
    o, p = tm.calculate_o_p_ext(most_likely, hi_lambda_expected, hi_lambda_sigma ** 2, est.LAMBDA)
    assert o == pytest.approx(1)
    assert p == pytest.approx(4)

    assert low_lambda_expected > hi_lambda_expected
    assert low_lambda_sigma > hi_lambda_sigma


@pytest.mark.dependency(depends=["test_pert"])
def test_ability_to_deduce_source_triple_from_pert():
    _test_triple(0, 0, 0)
    _test_triple(1, 1, 1)
    _test_triple(1, 2, 3)
    _test_triple(2, 5, 5)
    _test_triple(1, 2, 8)
    _test_triple(2, 3, 20)
    _test_triple(3, 8, 13)
    _test_triple(5, 13, 21)


def test_input():
    estinp = tm.EstimInput(0)
    estinp2 = tm.EstimInput(0.1)
    estinp3 = tm.EstimInput(0.25)

    assert estinp.distance_from(estinp) == 0
    assert estinp2.distance_from(estinp2) == 0
    assert estinp.distance_from(estinp2) > 0
    assert estinp.distance_from(estinp2) == estinp2.distance_from(estinp)
    assert (estinp.distance_from(estinp3)
            < estinp.distance_from(estinp2) + estinp2.distance_from(estinp3))


def create_histogram(dom, samples):
    dx = dom[1] - dom[0]
    bins_borders = list(dom - dx / 2.0) + [dom[-1] + dx / 2.0]
    histogram, _ = np.histogram(samples, bins=bins_borders)
    return histogram


def assert_sampling_corresponds_to_pdf(domain, generated, predicted, relative_diff=0.05):
    histogram = create_histogram(domain, generated).astype(float)
    histogram /= np.sum(histogram)

    predicted /= np.sum(predicted)
    histogram /= np.max(predicted)

    predicted /= np.max(predicted)

    high_diff = np.quantile(np.abs(predicted - histogram), 0.90)
    if high_diff > relative_diff:
        plot_diffs(domain, histogram, predicted)
    assert high_diff < relative_diff


def plot_diffs(dom, histogram, predicted):
    import matplotlib
    import matplotlib.pyplot as plt
    matplotlib.use("Agg")
    fig, ax = plt.subplots()
    ax.plot(dom, histogram, label="simulation")
    ax.plot(dom, predicted, label="prediction")
    ax.legend()
    ax.grid()
    fig.savefig("testfail.png")


def test_rv_algebra_addition():
    num_trials = 200000
    num_samples = 50

    e1 = tm.Estimate.from_triple(4, 2, 8)
    generated_pert = e1.pert_rvs(num_trials)
    dom, computed_pert = e1.get_pert(num_samples)
    assert_sampling_corresponds_to_pdf(dom, generated_pert, computed_pert)

    e2 = tm.Estimate.from_triple(8, 7, 8)
    generated_pert = e2.pert_rvs(num_trials)
    dom, computed_pert = e2.get_pert(num_samples)
    assert_sampling_corresponds_to_pdf(dom, generated_pert, computed_pert)

    generated_pert += e1.pert_rvs(num_trials)
    e3 = e2 + e1
    dom, computed_pert = e1.get_composed_pert(e2, 50)
    assert_sampling_corresponds_to_pdf(dom, generated_pert, computed_pert)

    dom, computed_pert = e3.get_pert(num_samples)
    assert_sampling_corresponds_to_pdf(dom, generated_pert, computed_pert)


def plot_two_functions(dom1, hom1, dom2, hom2):
    import pylab as pyl
    f = pyl.figure()
    plt = f.add_subplot()
    plt.plot(dom1, hom1)
    plt.plot(dom2, hom2)
    plt.grid()
    pyl.show()
    f.savefig("lala.png")


def _test_consistency_of_triple(triple):
    o0, m0, p0, gamma = triple
    est = tm.Estimate.from_triple(m0, o0, p0, gamma)
    rv = est._get_rv()
    o, p, m = tm.calculate_o_p_m_ext(rv.mean(), rv.var(), rv.stats("s"), gamma)
    assert o == pytest.approx(o0)
    assert p == pytest.approx(p0)
    assert m == pytest.approx(m0)


def test_compute_from_EVS():
    test_triples = (
            (2, 4, 6, 4),
            (2, 4, 10, 4),
            (1, 4, 5, 4),
            (1, 4, 4, 4),
            (1, 1, 4, 4),
            (2, 4, 20, 8),
    )
    for triple in test_triples:
        _test_consistency_of_triple(triple)
