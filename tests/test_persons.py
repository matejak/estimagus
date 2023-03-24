import pytest
import numpy as np

import estimage.persons as tm

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


def test_persons_workload(exclusive_target, shared_target):
    targets = []
    workload = tm.Workload.of_person("none", targets)
    assert workload.points == 0
    assert len(workload.targets) == 0

    targets = [exclusive_target]
    workload = tm.Workload.of_person("associate", targets)
    assert workload.points == exclusive_target.point_cost
    assert len(workload.targets) == 1
    assert workload.targets[0] == exclusive_target.name

    targets = [shared_target]
    workload = tm.Workload.of_person("associate", targets)
    assert workload.points == shared_target.point_cost / 2.0
    assert len(workload.targets) == 1
    assert workload.targets[0] == shared_target.name

    targets = [shared_target, exclusive_target]
    workload = tm.Workload.of_person("associate", targets)
    assert workload.points == shared_target.point_cost / 2.0 + exclusive_target.point_cost
    assert len(workload.targets) == 2
    assert workload.point_parts["feal"] == exclusive_target.point_cost
    assert workload.proportions["feal"] == 1
    assert workload.proportions["leaf"] == 0.5


def test_get_all_collaborators(shared_target, exclusive_target):
    assert len(tm.get_all_collaborators([])) == 0

    found = tm.get_all_collaborators([exclusive_target])
    assert len(found) == 1
    assert "associate" in found

    found = tm.get_all_collaborators([exclusive_target, shared_target])
    assert len(found) == 2
    assert "associate" in found
    assert "parallel_associate" in found


def test_get_all_workloads(shared_target, exclusive_target):
    workloads = tm.get_all_workloads([])
    assert len(workloads) == 0

    workloads = tm.get_all_workloads([shared_target, exclusive_target])
    assert len(workloads) == 2


def test_generate_target_occupation():
    task_sizes = [1]
    persons_potential = [1]
    bub = tm.gen_bub(task_sizes, persons_potential)
    assert len(bub) == 2
    assert bub[0] == - bub[1]

    task_sizes = [1]
    persons_potential = [1, 1]
    bub = tm.gen_bub(task_sizes, persons_potential)
    assert bub[0] == - bub[1]
    assert bub[0] == bub[2]
    assert bub[0] == task_sizes[0] / sum(persons_potential)
    assert len(bub) == len(persons_potential) * 2

    task_sizes = [2]
    persons_potential = [1, 0]
    bub = tm.gen_bub(task_sizes, persons_potential)
    assert bub[0] == - bub[1]
    assert bub[0] == sum(task_sizes)
    assert bub[2] == 0
    assert len(bub) == len(persons_potential) * 2


def test_generate_objective_function():
    task_sizes = [1]
    persons_potential = [1]
    c = tm.gen_c(task_sizes, persons_potential)
    assert len(c) == len(task_sizes) * len(persons_potential) + 2 * len(persons_potential)
    assert c[0] == 0
    assert c[-2] == 1
    assert c[-1] == 0

    task_sizes = [1, 1]
    persons_potential = [1]
    c = tm.gen_c(task_sizes, persons_potential)
    assert len(c) == len(task_sizes) * len(persons_potential) + 2 * len(persons_potential)
    assert c[0] == 0
    assert c[1] == 0
    assert c[-2] == 1
    assert c[-1] == 0

    task_sizes = [1, 1]
    persons_potential = [1, 1, 1]
    c = tm.gen_c(task_sizes, persons_potential)
    assert len(c) == len(task_sizes) * len(persons_potential) + 2 * len(persons_potential)
    assert sum(c) == len(persons_potential)
    assert np.all(c[-1::-2] == 0)


def test_generate_upper_bound_matrix():
    task_sizes = [1]
    persons_potential = [1]
    Aub = tm.gen_Aub(task_sizes, persons_potential)
    assert Aub.shape == (2, 3)
    assert Aub[0, 0] == 1
    assert Aub[-1, -1] == -1

    task_sizes = [1, 1]
    persons_potential = [1]
    Aub = tm.gen_Aub(task_sizes, persons_potential)
    assert Aub.shape == (2, 4)
    assert Aub[0, 0] == 1
    assert Aub[0, 1] == 1
    assert Aub[1, 0] == -1
    assert Aub[1, 1] == -1
    assert Aub[-1, -1] == -1

    task_sizes = [1, 1]
    persons_potential = [1, 1, 1]
    Aub = tm.gen_Aub(task_sizes, persons_potential)
    assert Aub.shape == (6, 12)
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
    assert Aeq.shape == (2, 3)
    assert Aeq[0, 0] == 1
    assert Aeq[-1, -2] == 1
    assert Aeq[-1, -1] == -1

    task_sizes = [1, 1]
    persons_potential = [1]
    Aeq = tm.gen_Aeq(task_sizes, persons_potential)
    assert Aeq.shape == (3, 4)
    assert Aeq[0, 0] == 1
    assert Aeq[0, 1] == 0
    assert Aeq[1, 0] == 0
    assert Aeq[1, 1] == 1
    assert Aeq[-1, -2] == 1
    assert Aeq[-1, -1] == -1

    task_sizes = [1, 1]
    persons_potential = [1, 1, 1]
    Aeq = tm.gen_Aeq(task_sizes, persons_potential)
    assert Aeq.shape == (5, 12)
    assert Aeq[0, 0] == 1
    assert Aeq[0, 1] == 0
    assert Aeq[1, 0] == 0
    assert Aeq[1, 1] == 1
    assert Aeq[-2, -4] == 1
    assert Aeq[-2, -3] == -1
    assert Aeq[-1, -2] == 1
    assert Aeq[-1, -1] == -1

    labor_cost = np.ones((len(persons_potential), len(task_sizes)))
    labor_cost[1, 1] = np.inf
    Aeq = tm.gen_Aeq(task_sizes, persons_potential, labor_cost)
    assert Aeq[-1, len(task_sizes) + 1] == 1


def test_generate_equality_rhs():
    task_sizes = [1]
    persons_potential = [1]
    beq = tm.gen_beq(task_sizes, persons_potential)
    assert len(beq) == (len(task_sizes) + len(persons_potential))
    assert sum(beq) == sum(task_sizes)
    assert np.all(beq[len(task_sizes):] == 0)

    task_sizes = [1, 3]
    persons_potential = [1, 2, 1]
    beq = tm.gen_beq(task_sizes, persons_potential)
    assert len(beq) == (len(task_sizes) + len(persons_potential))
    assert sum(beq) == sum(task_sizes)
    assert np.all(beq[len(task_sizes):] == 0)

    labor_cost = np.ones((len(persons_potential), len(task_sizes)))
    labor_cost[1, 1] = np.inf
    beq = tm.gen_beq(task_sizes, persons_potential, labor_cost)
    assert len(beq) == (len(task_sizes) + len(persons_potential) + 1)


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
    targets = [exclusive_target]
    workloads = tm.Workloads(targets)
    assert workloads.targets_by_name[exclusive_target.name] == exclusive_target
    assert workloads.collaborators_potential["associate"] == 1
    assert workloads.zmatrix()[0, 0] == 1

    targets = [exclusive_target, shared_target]
    workloads = tm.Workloads(targets)
    assert workloads.targets_by_name[exclusive_target.name] == exclusive_target
    assert workloads.zmatrix()[workloads.collab_indices["parallel_associate"], workloads.target_indices[exclusive_target.name]] == np.inf
    assert sum(workloads.zmatrix()[workloads.collab_indices["associate"], :]) == 2
    workloads.solve_problem()