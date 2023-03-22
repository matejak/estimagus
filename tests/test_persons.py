import pytest

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
