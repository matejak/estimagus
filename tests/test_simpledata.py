import pytest

from estimage import simpledata as tm
from estimage import data

from test_target import leaf_target, subtree_target


def test_obtaining_model_considers_leaf_target_values(leaf_target, subtree_target):
    model = tm.get_model([leaf_target])
    assert model.point_estimate.expected > 0
    assert model.point_estimate.expected == leaf_target.point_cost

    model = tm.get_model([subtree_target])
    assert model.point_estimate.expected == leaf_target.point_cost


def test_obtaining_model_overriden_by_pollster(leaf_target):
    pollster = data.MemoryPollster()

    model = tm.get_model([leaf_target])
    pollster.inform_results(model.get_all_task_models())
    assert model.point_estimate.expected == leaf_target.point_cost
    assert model.point_estimate_of(leaf_target.name).expected == leaf_target.point_cost

    pollster.tell_points(leaf_target.name, data.EstimInput(99))
    pollster.inform_results(model.get_all_task_models())
    assert model.point_estimate_of(leaf_target.name).expected == 99


def test_obtaining_model_overriden_by_pollster(leaf_target):
    pollster = data.MemoryPollster()

    model = tm.get_model([leaf_target])
    pollster.inform_results(model.get_all_task_models())
    assert model.point_estimate.expected == leaf_target.point_cost
    assert model.point_estimate_of(leaf_target.name).expected == leaf_target.point_cost

    pollster.tell_points(leaf_target.name, data.EstimInput(99))
    pollster.inform_results(model.get_all_task_models())
    assert model.point_estimate_of(leaf_target.name).expected == 99


@pytest.fixture
def bunch_of_tasks():
    name_estimate_map = dict(
        net_zero=data.Estimate(0, 0),
        net_two=data.Estimate(2, 0),
        second_net_two=data.Estimate(2, 0),
        thin_two=data.Estimate(2, 0.3),
    )
    ret = []
    for name, estimate in name_estimate_map.items():
        task = data.TaskModel(name)
        task.point_estimate = estimate
        ret.append(task)
    return ret


def test_get_no_similar_tasks(bunch_of_tasks):
    assert tm.order_nearby_tasks(data.TaskModel(""), [], 0, 0) == []
    assert tm.order_nearby_tasks(data.TaskModel("net_zero"), bunch_of_tasks, 0, 0) == []


def test_get_net_matches(bunch_of_tasks):
    reference = data.TaskModel("")
    reference.point_estimate = data.Estimate(0, 0)
    net_zeros = tm.order_nearby_tasks(reference, bunch_of_tasks, 0, 0)
    assert len(net_zeros) == 1
    assert net_zeros[0].name == "net_zero"

    reference.point_estimate = data.Estimate(2, 0)
    twos = tm.order_nearby_tasks(reference, bunch_of_tasks, 0, 0)
    assert len(twos) == 3


def test_similarity_of_masked_tasks(bunch_of_tasks):
    reference = data.TaskModel("")
    reference.point_estimate = data.Estimate(2, 0)
    for task in bunch_of_tasks:
        task.mask()
    net_twos = tm.order_nearby_tasks(reference, bunch_of_tasks, 0, 0)
    assert len(net_twos) == 3
