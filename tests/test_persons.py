import pytest
import numpy as np

import estimage.persons as tm
import estimage.simpledata
import estimage.data as data

from test_target import leaf_target, standalone_leaf_target


@pytest.fixture
def shared_target(leaf_target):
    leaf_target.collaborators.append("associate")
    leaf_target.collaborators.append("parallel_associate")
    return leaf_target


@pytest.fixture
def exclusive_target(standalone_leaf_target):
    standalone_leaf_target.collaborators.append("associate")
    return standalone_leaf_target


def evaluate_workloads(workloads):
    total_assigned_points = 0
    for person_name, potential in workloads.persons_potential.items():
        assigned_points = workloads.of_person(person_name).points
        if potential == 0:
            assert assigned_points == 0
        total_assigned_points += assigned_points
    assert total_assigned_points == pytest.approx(workloads.points)


def test_target_association(shared_target):
    target = data.BaseTarget()
    assert len(tm.get_people_associaged_with(target)) == 0

    target.collaborators = ["lu", "men"]
    assert len(tm.get_people_associaged_with(target)) == 2
    assert "lu" in tm.get_people_associaged_with(target)

    target.assignee = "ru"
    assert len(tm.get_people_associaged_with(target)) == 3
    assert "ru" in tm.get_people_associaged_with(target)

    target.collaborators = [""]
    assert len(tm.get_people_associaged_with(target)) == 1
    assert "ru" in tm.get_people_associaged_with(target)


def test_persons_workload(exclusive_target, shared_target):
    targets = []
    model = estimage.simpledata.get_model(targets)
    workloads = tm.SimpleWorkloads(targets, model)
    workloads.solve_problem()
    evaluate_workloads(workloads)
    assert workloads.points == 0
    assert not workloads.persons_potential
    persons_workload = workloads.of_person("none")
    assert persons_workload.name == "none"
    assert persons_workload.points == 0
    assert len(persons_workload.targets) == 0
    assert not workloads.get_who_works_on("something")

    targets = [exclusive_target]
    model = estimage.simpledata.get_model(targets)
    workloads = tm.SimpleWorkloads(targets, model)
    workloads.solve_problem()
    evaluate_workloads(workloads)
    assert len(workloads.persons_potential) == 1
    working_group = workloads.get_who_works_on(exclusive_target.name)
    assert len(working_group) == 1
    assert "associate" in working_group
    persons_workload = workloads.of_person("associate")
    assert persons_workload.points == exclusive_target.point_cost
    assert len(persons_workload.targets) == 1
    assert persons_workload.targets[0] == exclusive_target
    assert workloads.persons_potential["associate"] == 1.0

    targets = [shared_target]
    model = estimage.simpledata.get_model(targets)
    workloads = tm.SimpleWorkloads(targets, model)
    workloads.solve_problem()
    evaluate_workloads(workloads)
    persons_workload = workloads.of_person("associate")
    assert persons_workload.points == shared_target.point_cost / 2.0
    assert len(persons_workload.targets) == 1
    assert persons_workload.targets[0] == shared_target

    targets = [shared_target, exclusive_target]
    model = estimage.simpledata.get_model(targets)
    workloads = tm.SimpleWorkloads(targets, model)
    workloads.solve_problem()
    evaluate_workloads(workloads)
    persons_workload = workloads.of_person("associate")
    assert persons_workload.points == shared_target.point_cost / 2.0 + exclusive_target.point_cost
    assert len(persons_workload.targets) == 2
    assert persons_workload.point_parts["feal"] == exclusive_target.point_cost
    assert persons_workload.proportions["feal"] == 1
    assert persons_workload.proportions["leaf"] == 0.5
    workloads = tm.SimpleWorkloads(targets, model)
    workloads.persons_potential["parallel_associate"] = 0
    workloads.solve_problem()
    evaluate_workloads(workloads)


def test_get_all_collaborators(shared_target, exclusive_target):
    assert len(tm.get_all_collaborators([])) == 0

    found = tm.get_all_collaborators([exclusive_target])
    assert len(found) == 1
    assert "associate" in found

    found = tm.get_all_collaborators([exclusive_target, shared_target])
    assert len(found) == 2
    assert "associate" in found
    assert "parallel_associate" in found


def test_generate_target_occupation():
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


def test_workloads(exclusive_target, shared_target):
    targets = []
    model = estimage.simpledata.get_model(targets)
    workloads = tm.OptimizedWorkloads(targets, model)
    workloads.solve_problem()

    targets = [exclusive_target]
    model = estimage.simpledata.get_model(targets)
    workloads = tm.OptimizedWorkloads(targets, model)
    assert workloads.targets_by_name[exclusive_target.name] == exclusive_target
    assert workloads.persons_potential["associate"] == 1
    assert workloads.cost_matrix()[0, 0] == 1
    workloads.solve_problem()
    summary = workloads.summary()
    assert summary.expected_effort_of_full_potential == exclusive_target.point_cost

    targets = [exclusive_target, shared_target]
    model = estimage.simpledata.get_model(targets)
    workloads = tm.OptimizedWorkloads(targets, model)
    assert workloads.targets_by_name[exclusive_target.name] == exclusive_target
    assert workloads.cost_matrix()[workloads.persons_indices["parallel_associate"], workloads.targets_indices[exclusive_target.name]] == np.inf
    assert sum(workloads.cost_matrix()[workloads.persons_indices["associate"], :]) == 2
    workloads.persons_potential["associate"] = 1
    workloads.persons_potential["parallel_associate"] = 0.5
    workloads.solve_problem()
    summary = workloads.summary()
    assert summary.expected_effort_of_full_potential == (
        exclusive_target.point_cost + shared_target.point_cost) / 1.5
