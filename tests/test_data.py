import math

import pytest
import numpy as np
import scipy as sp
import scipy.stats

import estimage.data as tm
from estimage.entities import estimate


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

    deduced_expected_value = tm.pert_compute_expected_value(pert[0], pert[1])
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


def test_composition():
    c = tm.Composition("c")
    assert c.nominal_time_estimate.expected == 0
    assert c.nominal_point_estimate.expected == 0
    assert len(c.elements) == 0

    leaves = c.get_contained_elements()
    assert len(leaves) == 0

    e1 = tm.TaskModel("foo")
    e1.point_estimate = tm.Estimate(2, 1)
    e1.time_estimate = tm.Estimate(1, 1)

    c.add_element(e1)
    assert c.nominal_point_estimate.expected == 2

    leaves = c.get_contained_elements()
    assert len(leaves) == 1
    assert leaves[0] == e1

    c2 = tm.Composition("c2")
    c2.add_element(e1)
    c2.add_element(e1)
    assert c2.nominal_point_estimate.expected == 4
    assert c2.nominal_point_estimate.sigma == math.sqrt(2)
    c.add_composition(c2)
    assert c.nominal_point_estimate.expected == 6
    assert c.nominal_time_estimate.expected == 3

    leaves = c.get_contained_elements()
    assert len(leaves) == 3
    assert leaves[0] == e1
    assert leaves[-1] == e1

    e1.mask()
    assert c.remaining_point_estimate.expected == 0
    assert c.nominal_point_estimate.expected == 6
    e1.unmask()
    assert c.nominal_point_estimate.expected == 6
    assert c.remaining_point_estimate.expected == 6
    c2.mask()
    assert c2.remaining_point_estimate.expected == 0
    assert c.remaining_point_estimate.expected == 2
    c2.unmask()
    assert c.remaining_point_estimate.expected == 6


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


def test_supply():
    est = tm.EstiModel()

    e1 = tm.TaskModel("foo")
    est.add_element(e1)

    user_input = tm.EstimInput(1)

    est.estimate_points_of("foo", user_input)
    assert est.main_composition.nominal_point_estimate.expected == 1

    user_input = tm.EstimInput(2)

    est.estimate_time_of("foo", user_input)
    assert est.main_composition.nominal_time_estimate.expected == 2

    with pytest.raises(RuntimeError):
        est.add_element(e1)

    target = est.export_element("foo")
    assert target.point_cost == 1
    assert target.time_cost == 2

    assert est.main_composition.nominal_time_estimate.expected == 2

    est.complete_element("foo")
    assert est.main_composition.nominal_point_estimate.expected == 0
    assert est.main_composition.nominal_time_estimate.expected == 0

    est.new_element("bar")
    est.estimate_points_of("bar", user_input)
    assert est.main_composition.nominal_point_estimate.expected == 2

    model2 = tm.EstiModel()
    t1 = tm.TaskModel("baz")
    t1.point_estimate = tm.Estimate(3, 0)
    t2 = tm.TaskModel("bar")
    t2.point_estimate = tm.Estimate(2, 0)
    c = tm.Composition("1")
    c.add_element(t1)
    c2 = tm.Composition("2")
    c.add_composition(c2)
    c2.add_element(t2)
    model2.use_composition(c)
    assert model2.nominal_point_estimate_of("bar").expected == 2
    assert model2.nominal_point_estimate_of("baz").expected == 3
    assert model2.nominal_point_estimate_of("2").expected == 2
    assert model2.nominal_point_estimate.expected == 5


def test_model_updates_targets():
    target_one = tm.BaseTarget("one")
    target_one.point_cost = 5

    model = tm.EstiModel()
    targets = [target_one]
    model.use_composition(target_one.to_tree(targets))
    target_one.point_cost = 4

    target_two = tm.BaseTarget("two")
    target_two.point_cost = 1
    targets.append(target_two)

    assert model.export_element("one").point_cost == 5
    model.update_targets_with_values(targets)
    assert targets[0].point_cost == 5


def test_model_updates_nested_targets():
    target_one = tm.BaseTarget("one")
    target_one.point_cost = 5

    target_two = tm.BaseTarget("two")
    target_two.point_cost = 1
    target_two.dependents.append(target_one)

    model = tm.EstiModel()
    targets = [target_two]
    model.use_composition(target_two.to_tree(targets))
    target_one.point_cost = 4

    model.update_targets_with_values(targets)
    assert target_one.point_cost == 5
    assert target_two.point_cost == 1


def test_memory_types():
    r1 = tm.MemoryTaskModel("R")
    r1.set_point_estimate(3, 2, 4)
    r1.save()
    r1.set_point_estimate(2, 1, 3)

    r2 = tm.MemoryTaskModel("RR")
    r2.set_time_estimate(3, 2, 4)
    r2.save()

    r12 = tm.MemoryTaskModel.load("R")
    assert r12.nominal_point_estimate.expected == 3
    r1.save()
    r12 = tm.MemoryTaskModel.load("R")
    assert r12.nominal_point_estimate.expected == r1.nominal_point_estimate.expected

    r22 = tm.MemoryTaskModel.load("RR")
    assert r22.nominal_time_estimate.expected == 3

    c1 = tm.MemoryComposition("C")
    c1.add_element(r1)
    c2 = tm.MemoryComposition("D")
    c1.add_composition(c2)
    c2.add_element(r2)

    c1.save()
    c3 = tm.MemoryComposition.load("C")
    assert c3.elements[0].nominal_point_estimate.expected == r1.nominal_point_estimate.expected
    c4 = c3.compositions[0]
    assert c4.elements[0].nominal_time_estimate.expected == r2.nominal_time_estimate.expected


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

    high_diff = np.quantile(np.abs(predicted - histogram), 0.95)
    # plot_diffs(domain, histogram, predicted)
    assert high_diff < relative_diff


def plot_diffs(dom, histogram, predicted):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot(dom, histogram, label="simulation")
    ax.plot(dom, predicted, label="prediction")
    ax.legend()
    ax.grid()
    plt.show()


def test_rv_algebra_addition():
    num_trials = 400000
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


def test_rv_algebra_gauss_division():
    num_trials = 100000
    num_samples = 100

    dom = np.linspace(0.2, 2, num_samples)
    generated_normal = sp.stats.norm.rvs(loc=1.5, scale=0.4, size=num_trials)
    divided = 1.0 / generated_normal
    # divided[generated_normal == 0] = np.inf
    real_reciprocal_normal = estimate.reciprocal_normal_pdf(dom, 1.5, 0.4)
    assert_sampling_corresponds_to_pdf(dom, divided, real_reciprocal_normal)


def test_rv_algebra_division():
    num_trials = 100000
    num_samples = 100

    gauss_mean = 1.5
    gauss_std = 0.4

    e1 = tm.Estimate.from_triple(0, 0, 0)
    pdf = e1.divide_by_gauss_pdf(num_samples, gauss_mean, gauss_std)
    np.testing.assert_array_equal(pdf[1], 0)

    e1 = tm.Estimate.from_triple(2, 2, 2)
    dom, pdf = e1.divide_by_gauss_pdf(num_samples, gauss_mean, gauss_std)
    assert dom[0] > 0.05 * e1.expected
    assert pdf[0] < 0.01
    assert dom[-1] < 4 * e1.expected
    assert pdf[-1] < 0.05
    generated_pert = e1.pert_rvs(num_trials)
    generated_normal = sp.stats.norm.rvs(loc=gauss_mean, scale=gauss_std, size=num_trials)
    assert_sampling_corresponds_to_pdf(dom, generated_pert / generated_normal, pdf)

    e1 = tm.Estimate.from_triple(5, 3, 10)
    dom, pdf = e1.divide_by_gauss_pdf(num_samples, gauss_mean, gauss_std)
    generated_pert = e1.pert_rvs(num_trials)
    generated_normal = sp.stats.norm.rvs(loc=gauss_mean, scale=gauss_std, size=num_trials)
    assert_sampling_corresponds_to_pdf(dom, generated_pert / generated_normal, pdf)

    gauss_mean = 2
    gauss_std = 0.4
    e1 = tm.Estimate.from_triple(80, 60, 140)
    dom, pdf = e1.divide_by_gauss_pdf(num_samples, gauss_mean, gauss_std)
    generated_pert = e1.pert_rvs(num_trials)
    generated_normal = sp.stats.norm.rvs(loc=gauss_mean, scale=gauss_std, size=num_trials)
    assert_sampling_corresponds_to_pdf(dom, generated_pert / generated_normal, pdf)
