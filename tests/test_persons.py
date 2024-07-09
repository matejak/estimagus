import pytest
import numpy as np

import estimage.persons as tm
import estimage.simpledata
import estimage.data as data

from test_card import leaf_card, standalone_leaf_card


def _value_from_dict(d):
    return next(iter(d.values()))


@pytest.fixture
def shared_card(leaf_card):
    leaf_card.collaborators.append("associate")
    leaf_card.collaborators.append("parallel_associate")
    return leaf_card


@pytest.fixture
def exclusive_card(standalone_leaf_card):
    standalone_leaf_card.collaborators.append("associate")
    return standalone_leaf_card


def evaluate_workloads(workloads):
    total_assigned_points = 0
    for person_name, potential in workloads.persons_potential.items():
        assigned_points = workloads.of_person(person_name).points
        if potential == 0:
            assert assigned_points == 0
        total_assigned_points += assigned_points
    assert total_assigned_points == pytest.approx(workloads.points)


def test_card_association(shared_card):
    card = data.BaseCard("")
    assert len(tm.get_people_associaged_with(card)) == 0

    card.collaborators = ["lu", "men"]
    assert len(tm.get_people_associaged_with(card)) == 2
    assert "lu" in tm.get_people_associaged_with(card)

    card.assignee = "ru"
    assert len(tm.get_people_associaged_with(card)) == 3
    assert "ru" in tm.get_people_associaged_with(card)

    card.collaborators = [""]
    assert len(tm.get_people_associaged_with(card)) == 1
    assert "ru" in tm.get_people_associaged_with(card)


def test_persons_workload(exclusive_card, shared_card):
    cards = []
    model = estimage.simpledata.get_model(cards)
    workloads = tm.SimpleWorkloads(cards, model)
    workloads.solve_problem()
    evaluate_workloads(workloads)
    assert workloads.points == 0
    assert not workloads.persons_potential
    persons_workload = workloads.of_person("none")
    assert persons_workload.name == "none"
    assert persons_workload.points == 0
    assert len(persons_workload.cards_by_name) == 0
    assert not workloads.get_who_works_on("something")

    cards = [exclusive_card]
    model = estimage.simpledata.get_model(cards)
    workloads = tm.SimpleWorkloads(cards, model)
    workloads.solve_problem()
    evaluate_workloads(workloads)
    assert len(workloads.persons_potential) == 1
    working_group = workloads.get_who_works_on(exclusive_card.name)
    assert len(working_group) == 1
    assert "associate" in working_group
    persons_workload = workloads.of_person("associate")
    assert persons_workload.points == exclusive_card.point_cost
    assert len(persons_workload.cards_by_name) == 1
    assert _value_from_dict(persons_workload.cards_by_name) == exclusive_card
    assert workloads.persons_potential["associate"] == 1.0

    cards = [shared_card]
    model = estimage.simpledata.get_model(cards)
    workloads = tm.SimpleWorkloads(cards, model)
    workloads.solve_problem()
    evaluate_workloads(workloads)
    persons_workload = workloads.of_person("associate")
    assert persons_workload.points == shared_card.point_cost / 2.0
    assert len(persons_workload.cards_by_name) == 1
    assert _value_from_dict(persons_workload.cards_by_name) == shared_card

    cards = [shared_card, exclusive_card]
    model = estimage.simpledata.get_model(cards)
    workloads = tm.SimpleWorkloads(cards, model)
    workloads.solve_problem()
    evaluate_workloads(workloads)
    persons_workload = workloads.of_person("associate")
    assert persons_workload.points == shared_card.point_cost / 2.0 + exclusive_card.point_cost
    assert len(persons_workload.cards_by_name) == 2
    assert persons_workload.point_parts["feal"] == exclusive_card.point_cost
    assert persons_workload.proportions["feal"] == 1
    assert persons_workload.proportions["leaf"] == 0.5
    workloads = tm.SimpleWorkloads(cards, model)
    workloads.persons_potential["parallel_associate"] = 0
    workloads.solve_problem()
    evaluate_workloads(workloads)


def test_get_all_collaborators(shared_card, exclusive_card):
    assert len(tm.get_all_collaborators([])) == 0

    found = tm.get_all_collaborators([exclusive_card])
    assert len(found) == 1
    assert "associate" in found

    found = tm.get_all_collaborators([exclusive_card, shared_card])
    assert len(found) == 2
    assert "associate" in found
    assert "parallel_associate" in found


def test_generate_card_occupation():
    task_sizes = [1]
    persons_potential = [1]
    bub = tm.gen_bub(task_sizes, persons_potential)
    assert len(bub) == 3
    assert bub[0] == - bub[1]

    task_sizes = [1]
    persons_potential = [1, 1]
    bub = tm.gen_bub(task_sizes, persons_potential)
    assert bub[0] == - bub[1]
    assert bub[0] == bub[2]
    assert bub[0] == task_sizes[0] / sum(persons_potential)
    assert len(bub) == len(persons_potential) * 3

    task_sizes = [2]
    persons_potential = [1, 0]
    bub = tm.gen_bub(task_sizes, persons_potential)
    assert bub[0] == - bub[1]
    assert bub[0] == sum(task_sizes)
    assert bub[2] == 0
    assert len(bub) == len(persons_potential) * 3


def test_generate_objective_function():
    task_sizes = [1]
    persons_potential = [1]
    c = tm.gen_c(task_sizes, persons_potential)
    assert len(c) == len(task_sizes) * len(persons_potential) + len(persons_potential) * 2 + 1
    assert c[0] == 0
    assert c[-1] == 1

    task_sizes = [1, 1]
    persons_potential = [1]
    c = tm.gen_c(task_sizes, persons_potential)
    assert len(c) == len(task_sizes) * len(persons_potential) + len(persons_potential) * 2 + 1
    assert c[0] == 0
    assert c[1] == 0
    assert c[-1] == 1

    task_sizes = [1, 1]
    persons_potential = [1, 1, 1]
    c = tm.gen_c(task_sizes, persons_potential)
    assert len(c) == len(task_sizes) * len(persons_potential) + len(persons_potential) * 2 + 1


def test_generate_upper_bound_matrix():
    task_sizes = [1]
    persons_potential = [1]
    Aub = tm.gen_Aub(task_sizes, persons_potential)
    assert Aub.shape == (3, 4)
    assert Aub[0, 0] == 1
    assert Aub[-1, -1] == -1

    task_sizes = [1, 1]
    persons_potential = [1]
    Aub = tm.gen_Aub(task_sizes, persons_potential)
    assert Aub.shape == (3, 5)
    assert Aub[0, 0] == 1
    assert Aub[0, 1] == 1
    assert Aub[1, 0] == -1
    assert Aub[1, 1] == -1
    assert Aub[-1, -1] == -1

    task_sizes = [1, 1]
    persons_potential = [1, 1, 1]
    Aub = tm.gen_Aub(task_sizes, persons_potential)
    assert Aub.shape == (9, 13)
    assert Aub[0, 0] == 1
    assert Aub[0, 1] == 1
    assert Aub[0, 2] == 0
    assert Aub[1, 0] == -1
    assert Aub[1, 1] == -1
    assert Aub[1, 2] == 0
    assert Aub[-1, -1] == -1


def test_generate_equality_matrix():
    task_sizes = [1]
    persons_potential = [1]
    Aeq = tm.gen_Aeq(task_sizes, persons_potential)
    assert Aeq.shape == (2, 4)
    assert Aeq[0, 0] == 1
    assert Aeq[-1, -1] == 0

    task_sizes = [1, 1]
    persons_potential = [1]
    Aeq = tm.gen_Aeq(task_sizes, persons_potential)
    assert Aeq.shape == (3, 5)
    assert Aeq[0, 0] == 1
    assert Aeq[0, 1] == 0
    assert Aeq[1, 0] == 0
    assert Aeq[1, 1] == 1
    assert Aeq[-1, -1] == 0

    task_sizes = [1, 1]
    persons_potential = [1, 1, 1]
    Aeq = tm.gen_Aeq(task_sizes, persons_potential)
    assert Aeq.shape == (5, 13)
    assert Aeq[0, 0] == 1
    assert Aeq[0, 1] == 0
    assert Aeq[1, 0] == 0
    assert Aeq[1, 1] == 1

    labor_cost = np.ones((len(persons_potential), len(task_sizes)))
    labor_cost[1, 1] = np.inf
    Aeq = tm.gen_Aeq(task_sizes, persons_potential, labor_cost)
    assert Aeq[-1 - len(persons_potential), len(task_sizes) + 1] == 1


def test_generate_equality_rhs():
    task_sizes = [1]
    persons_potential = [1]
    beq = tm.gen_beq(task_sizes, persons_potential)
    assert len(beq) == len(task_sizes) + len(persons_potential)
    assert sum(beq) == sum(task_sizes)
    assert np.all(beq[len(task_sizes):] == 0)

    task_sizes = [1, 3]
    persons_potential = [1, 2, 1]
    beq = tm.gen_beq(task_sizes, persons_potential)
    assert len(beq) == len(task_sizes) + len(persons_potential)
    assert sum(beq) == sum(task_sizes)
    assert np.all(beq[len(task_sizes):] == 0)

    labor_cost = np.ones((len(persons_potential), len(task_sizes)))
    labor_cost[1, 1] = np.inf
    beq = tm.gen_beq(task_sizes, persons_potential, labor_cost)
    assert len(beq) == len(task_sizes) + 1 + len(persons_potential)


def evaluate_solution(solution, task_sizes, persons_potential, labor_cost=None):
    assert solution.shape == (len(persons_potential), len(task_sizes))
    workloads_per_person = np.sum(solution, 1)
    normalized_workloads = workloads_per_person / np.array(persons_potential)
    normalized_workloads *= len(normalized_workloads) / sum(normalized_workloads)
    np.testing.assert_almost_equal(normalized_workloads, 1)
    assert sum(solution.flat) == pytest.approx(sum(task_sizes))
    for task_index, task_size in enumerate(task_sizes):
        assert sum(solution[:, task_index]) == pytest.approx(task_size)
    if labor_cost is not None:
        assert np.all(solution[labor_cost == np.inf] == 0)


def test_optimization():
    task_sizes = [1]
    persons_potential = [1]
    solution = tm.solve(task_sizes, persons_potential)
    evaluate_solution(solution, task_sizes, persons_potential)
    assert solution[0, 0] == 1

    task_sizes = [1, 5]
    persons_potential = [1]
    solution = tm.solve(task_sizes, persons_potential)
    evaluate_solution(solution, task_sizes, persons_potential)
    assert solution[0, 0] == 1
    assert solution[0, 1] == 5

    task_sizes = [1, 2]
    persons_potential = [1, 3]
    solution = tm.solve(task_sizes, persons_potential)
    evaluate_solution(solution, task_sizes, persons_potential)

    task_sizes = [1, 4, 2]
    persons_potential = [1, 0.5]
    solution = tm.solve(task_sizes, persons_potential)
    evaluate_solution(solution, task_sizes, persons_potential)

    labor_cost = np.ones((len(persons_potential), len(task_sizes)))
    labor_cost[1, 1] = np.inf
    labor_cost[0, 2] = np.inf
    solution = tm.solve(task_sizes, persons_potential, labor_cost)
    evaluate_solution(solution, task_sizes, persons_potential, labor_cost)


def test_workloads(exclusive_card, shared_card):
    cards = []
    model = estimage.simpledata.get_model(cards)
    workloads = tm.OptimizedWorkloads(cards, model)
    workloads.solve_problem()

    cards = [exclusive_card]
    model = estimage.simpledata.get_model(cards)
    workloads = tm.OptimizedWorkloads(cards, model)
    assert workloads.cards_by_name[exclusive_card.name] == exclusive_card
    assert workloads.persons_potential["associate"] == 1
    assert workloads.cost_matrix()[0, 0] == 1
    workloads.solve_problem()
    summary = workloads.summary()
    assert summary.expected_effort_of_full_potential == exclusive_card.point_cost

    cards = [exclusive_card, shared_card]
    model = estimage.simpledata.get_model(cards)
    workloads = tm.OptimizedWorkloads(cards, model)
    assert workloads.cards_by_name[exclusive_card.name] == exclusive_card
    assert workloads.cost_matrix()[workloads.persons_indices["parallel_associate"], workloads.cards_indices[exclusive_card.name]] == np.inf
    assert sum(workloads.cost_matrix()[workloads.persons_indices["associate"], :]) == 2
    workloads.persons_potential["associate"] = 1
    workloads.persons_potential["parallel_associate"] = 0.5
    workloads.solve_problem()
    summary = workloads.summary()
    assert summary.expected_effort_of_full_potential == (
        exclusive_card.point_cost + shared_card.point_cost) / 1.5
