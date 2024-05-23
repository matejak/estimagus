import math

import pytest

import estimage.data as tm


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

    card = est.export_element("foo")
    assert card.point_cost == 1
    assert card.time_cost == 2

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


def test_model_updates_cards():
    card_one = tm.BaseCard("one")
    card_one.point_cost = 5

    model = tm.EstiModel()
    cards = [card_one]
    model.use_composition(card_one.to_tree(cards))
    card_one.point_cost = 4

    card_two = tm.BaseCard("two")
    card_two.point_cost = 1
    cards.append(card_two)

    assert model.export_element("one").point_cost == 5
    model.update_cards_with_values(cards)
    assert cards[0].point_cost == 5


def test_model_updates_nested_cards():
    card_one = tm.BaseCard("one")
    card_one.point_cost = 5

    card_two = tm.BaseCard("two")
    card_two.point_cost = 1
    card_two.children.append(card_one)

    model = tm.EstiModel()
    cards = [card_two]
    model.use_composition(card_two.to_tree(cards))
    card_one.point_cost = 4

    model.update_cards_with_values(cards)
    assert card_one.point_cost == 5
    assert card_two.point_cost == 1


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
