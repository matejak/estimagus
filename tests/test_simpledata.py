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
