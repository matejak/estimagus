import math

import pytest
import numpy as np

import app.data as tm


def test_storage():
    el = tm.BaseTarget()
    cost = el.point_cost
    assert cost >= 0

    cost2 = el.time_cost
    assert cost2 >= 0

    assert el.parse_point_cost("5") == 5

    el.TIME_UNIT = "pw"
    assert el.parse_time_cost("5pw") == 5
    assert el.parse_time_cost("5 pw") == 5

    assert el.format_time_cost(8.2) == "8 pw"


@pytest.mark.dependency
def test_estimate():
    est = tm.Estimate.from_triple(4, 3, 6)
    assert est.expected > 4

    assert est.rank_distance(est) == 0

    certain_est = tm.Estimate.from_triple(1, 1, 1)
    different_certain_est = tm.Estimate.from_triple(2, 2, 2)
    assert certain_est.rank_distance(different_certain_est) == float("inf")
    assert different_certain_est.rank_distance(certain_est) == float("inf")

    est_centered = tm.Estimate.from_triple(4, 3, 5)
    est_broad = tm.Estimate.from_triple(4, 2, 6)
    assert est_centered.rank_distance(est) > est_broad.rank_distance(est)
    assert est_centered.rank_distance(est) == est.rank_distance(est_centered)


def index_of_value_in_array_closest_to(arr, value):
    difference = np.abs(arr - value)
    return np.argmin(difference)


def pert_test_estimate(est):
    pert = est.get_pert(100)
    assert pert.shape == (2, 100)
    assert pert[0][0] < est.source.optimistic
    assert pert[0][-1] > est.source.pessimistic
    assert pytest.approx(pert[1].sum() * (pert[0][1] - pert[0][0])) == 1
    index_of_most_likely = np.argmax(pert[1])
    assert est.source.most_likely == pytest.approx(pert[0][index_of_most_likely], 0.05)
    assert est.expected == pytest.approx(tm.pert_compute_expected_value(pert[0], pert[1]), 0.05)


@pytest.mark.dependency(depends=["test_estimate"])
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
    assert est.source.pessimistic > pert[0][0] > est.source.optimistic
    assert pert[1][0] == 1

    pert_test_estimate(est)
    est3 = tm.Estimate.from_triple(4, 3, 13)
    pert_test_estimate(est3)

    pert = est.get_pert(100)
    est2 = tm.Estimate.from_pert(pert[0], pert[1])
    assert est.expected == pytest.approx(est2.expected, 0.05)
    assert est.sigma == pytest.approx(est2.sigma, 0.05)

    assert pert[1].sum() == est.get_pert(201)[1].sum() * 0.5

    est_identical = est.compose_with(zero)
    assert est_identical.expected == est.expected
    assert est_identical.sigma == est.sigma

    est_shifted = est.compose_with(one)
    assert est_shifted.expected == est.expected + 1
    assert est_shifted.sigma == est.sigma

    est_composite = est.compose_with(est3)
    assert est3.expected + est.expected == pytest.approx(est_composite.expected, 0.05)
    assert math.sqrt(est3.sigma ** 2 + est.sigma ** 2) == pytest.approx(est_composite.sigma, 0.05)


def test_composition():
    c = tm.Composition("c")
    assert c.time_estimate.expected == 0
    assert c.point_estimate.expected == 0
    assert len(c.elements) == 0

    e1 = tm.TaskModel("foo")
    e1.point_estimate = tm.Estimate(2, 1)
    e1.time_estimate = tm.Estimate(1, 1)

    c.add_element(e1)
    assert c.point_estimate.expected == 2

    c2 = tm.Composition("c2")
    c2.add_element(e1)
    c2.add_element(e1)
    assert c2.point_estimate.expected == 4
    assert c2.point_estimate.sigma == math.sqrt(2)
    c.add_composition(c2)
    assert c.point_estimate.expected == 6
    assert c.time_estimate.expected == 3

    e1.mask()
    assert c.point_estimate.expected == 0
    e1.unmask()
    assert c.point_estimate.expected == 6
    c2.mask()
    assert c.point_estimate.expected == 2
    c2.unmask()
    assert c.point_estimate.expected == 6


def test_supply():
    est = tm.EstiModel()

    e1 = tm.TaskModel("foo")
    est.add_element(e1)

    user_input = tm.EstimInput(1)

    est.estimate_points_of("foo", user_input)
    assert est.main_composition.point_estimate.expected == 1

    user_input = tm.EstimInput(2)

    est.estimate_time_of("foo", user_input)
    assert est.main_composition.time_estimate.expected == 2

    with pytest.raises(RuntimeError):
        est.add_element(e1)

    target = est.export_element("foo")
    assert target.point_cost == 1
    assert target.time_cost == 2

    assert est.main_composition.time_estimate.expected == 2

    est.complete_element("foo")
    assert est.main_composition.point_estimate.expected == 0
    assert est.main_composition.time_estimate.expected == 0

    est.new_element("bar")
    est.estimate_points_of("bar", user_input)
    assert est.main_composition.point_estimate.expected == 2

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
    assert model2.point_estimate_of("bar").expected == 2
    assert model2.point_estimate_of("baz").expected == 3
    assert model2.point_estimate_of("2").expected == 2
    assert model2.point_estimate.expected == 5


def test_poll():
    pollster = tm.MemoryPollster()

    point_input = pollster.ask_points("foo")
    assert point_input.most_likely == 0

    hint = tm.EstimInput(1)

    assert not pollster.knows_points("foo")
    pollster.tell_points("foo", hint)
    assert pollster.knows_points("foo")
    point_input = pollster.ask_points("foo")

    assert point_input.most_likely == 1


def test_pollster_fills_in():
    result = tm.TaskModel("esti")
    pollster = tm.MemoryPollster()
    pollster.tell_points("esti", tm.EstimInput(2))
    pollster.inform_results([result])
    assert result.point_estimate.expected == 2

    estimodel = tm.EstiModel()
    estimodel.new_element("esti")

    all_results = estimodel.get_all_task_models()
    pollster.inform_results(all_results)
    assert estimodel.point_estimate.expected == 2

    estimodel.new_element("xsti")
    pollster.tell_points("xsti", tm.EstimInput(3))

    all_results = estimodel.get_all_task_models()
    pollster.inform_results(all_results)
    assert estimodel.point_estimate.expected == 5


def test_integrate():
    pollster = tm.MemoryPollster()
    est = tm.EstiModel()

    name1 = "foo"
    e1 = tm.TaskModel(name1)
    est.add_element(e1)

    pollster.tell_points(name1, tm.EstimInput(3))
    user_point_input = pollster.ask_points(name1)
    est.estimate_points_of(name1, user_point_input)

    name2 = "bar"
    e2 = tm.TaskModel(name2)
    est.add_element(e2)

    pollster.tell_points(name2, tm.EstimInput(5))
    user_point_input = pollster.ask_points(name2)

    est.estimate_points_of(name2, user_point_input)

    assert e1.point_estimate.expected == 3
    assert e1.point_estimate.variance == 0
    assert e2.point_estimate.expected == 5

    assert est.main_composition.point_estimate.expected == 8
    assert est.main_composition.point_estimate.variance == 0


def test_memory_types():
    r1 = tm.MemoryTaskModel("R")
    r1.set_point_estimate(3, 2, 4)
    r1.save()
    r1.set_point_estimate(2, 1, 3)

    r2 = tm.MemoryTaskModel("RR")
    r2.set_time_estimate(3, 2, 4)
    r2.save()

    r12 = tm.MemoryTaskModel.load("R")
    assert r12.point_estimate.expected == 3
    r1.save()
    r12 = tm.MemoryTaskModel.load("R")
    assert r12.point_estimate.expected == r1.point_estimate.expected

    r22 = tm.MemoryTaskModel.load("RR")
    assert r22.time_estimate.expected == 3

    c1 = tm.MemoryComposition("C")
    c1.add_element(r1)
    c2 = tm.MemoryComposition("D")
    c1.add_composition(c2)
    c2.add_element(r2)

    c1.save()
    c3 = tm.MemoryComposition.load("C")
    assert c3.elements[0].point_estimate.expected == r1.point_estimate.expected
    c4 = c3.compositions[0]
    assert c4.elements[0].time_estimate.expected == r2.time_estimate.expected


def test_target():
    target = tm.BaseTarget()
    target.name = "leaf"
    target.point_cost = 4
    target.time_cost = 3
    result = target.get_tree()
    assert target in target
    assert target.name == result.name
    assert target.point_cost == result.point_estimate.expected
    assert target.time_cost == result.time_estimate.expected

    complex_target = tm.BaseTarget()
    assert complex_target in complex_target
    assert target not in complex_target
    complex_target.add_element(target)
    assert target in complex_target
    assert complex_target not in target
    complex_target.name = "tree"
    composition = complex_target.get_tree()
    assert complex_target.name == composition.name
    assert len(composition.elements) == 1
    assert composition.elements[0].name == target.name
    assert target.point_cost == composition.point_estimate.expected
    assert target.time_cost == composition.time_estimate.expected

    complexer_target = tm.BaseTarget()
    assert target not in complexer_target
    complexer_target.add_element(complex_target)
    assert target in complexer_target
    assert complexer_target not in target
    complexer_target.name = "tree_of_trees"
    composition = complexer_target.get_tree()
    assert complexer_target.name == composition.name
    assert complex_target.name == composition.compositions[0].name
    assert target.name == composition.compositions[0].elements[0].name


@pytest.mark.dependency
def test_set_reduction():
    assert tm.reduce_subsets_from_sets([]) == []
    assert tm.reduce_subsets_from_sets(["a"]) == ["a"]
    assert tm.reduce_subsets_from_sets(["a", "a"]) == ["a"]
    assert tm.reduce_subsets_from_sets(["a", "b"]) == ["a", "b"]
    assert tm.reduce_subsets_from_sets(["a", "b", "axe"]) == ["b", "axe"]
    assert tm.reduce_subsets_from_sets(["a", "axe", "b"]) == ["axe", "b"]


@pytest.mark.dependency(depends=["test_set_reduction"])
def test_targets_to_tree():
    null_tree = tm.BaseTarget.to_tree([])
    assert null_tree == tm.Composition("")

    leaf = tm.BaseTarget()
    leaf.name = "leaf"
    tree = tm.BaseTarget.to_tree([leaf])
    assert tree == leaf.get_tree()
    assert tree == tm.BaseTarget.to_tree([leaf, leaf])

    feal = tm.BaseTarget()
    feal.name = "feal"
    result = tm.Composition("")
    result.add_element(feal.get_tree())
    result.add_element(leaf.get_tree())
    assert result == tm.BaseTarget.to_tree([feal, leaf])

    lower_tree = tm.BaseTarget()
    lower_tree.name = "lower tree"
    lower_tree.add_element(leaf)
    result = tm.Composition("")
    result.add_composition(lower_tree.get_tree())
    result.add_element(feal.get_tree())
    assert result == tm.BaseTarget.to_tree([leaf, lower_tree, feal])
