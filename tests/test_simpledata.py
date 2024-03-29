import pytest
import datetime

from estimage import simpledata as tm
from estimage import data
from estimage.persistence.pollster import memory

from test_card import leaf_card, subtree_card


def get_independent_memory_io():
    class ret(memory.MemoryPollsterIO):
        _memory = dict()
    return ret


def test_obtaining_model_considers_leaf_card_values(leaf_card, subtree_card):
    model = tm.get_model([leaf_card])
    assert model.nominal_point_estimate.expected > 0
    assert model.nominal_point_estimate.expected == leaf_card.point_cost

    model = tm.get_model([subtree_card])
    assert model.nominal_point_estimate.expected == leaf_card.point_cost


def test_empty_model():
    model = tm.get_model([])
    assert model.nominal_point_estimate.expected == 0


def test_obtaining_model_overriden_by_pollster(leaf_card):
    pollster = data.Pollster(memory.MemoryPollsterIO)

    model = tm.get_model([leaf_card])
    pollster.supply_valid_estimations_to_tasks(model.get_all_task_models())
    assert model.nominal_point_estimate.expected == leaf_card.point_cost
    assert model.nominal_point_estimate_of(leaf_card.name).expected == leaf_card.point_cost

    pollster.tell_points(leaf_card.name, data.EstimInput(99))
    pollster.supply_valid_estimations_to_tasks(model.get_all_task_models())
    assert model.nominal_point_estimate_of(leaf_card.name).expected == 99


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


def test_context():
    empty_pollster = data.Pollster(get_independent_memory_io())

    own_pollster = data.Pollster(get_independent_memory_io())
    own_pollster.tell_points("task", data.EstimInput(1))

    global_pollster = data.Pollster(get_independent_memory_io())
    global_pollster.tell_points("t", data.EstimInput(1))

    competing_pollster = data.Pollster(get_independent_memory_io())
    competing_pollster.tell_points("task", data.EstimInput(1))
    competing_pollster.tell_points("t", data.EstimInput(2))

    task = data.BaseCard("task")
    context = tm.Context(task)
    assert context.estimate_status == "absent"
    with pytest.raises(ValueError):
        context.own_estimation
    with pytest.raises(ValueError):
        context.estimation

    context.process_own_pollster(own_pollster)
    assert context.estimate_status == "single"
    assert context.own_estimation_exists
    assert not context.authoritative_record_exists
    assert not context.authoritative_record_consistent
    assert context.estimation_source == "own"
    assert not context.global_estimation_exists
    assert context.own_estimation.expected == 1
    assert context.estimation.expected == 1

    with pytest.raises(ValueError):
        context.global_estimation
    context.process_global_pollster(competing_pollster)
    assert context.estimation_source == "own"
    assert context.own_estimation_exists
    assert context.global_estimation_exists
    assert context.estimate_status == "duplicate"

    context.process_global_pollster(empty_pollster)
    context.process_own_pollster(empty_pollster)
    assert context.estimate_status == "absent"
    assert context.estimation_source == "none"

    task = data.BaseCard("t")
    task.point_cost = 1.2
    context = tm.Context(task)
    context.process_own_pollster(own_pollster)
    assert not context.own_estimation_exists
    assert context.authoritative_record_exists
    assert context.estimation_source == "none"
    assert context.estimate_status == "absent"
    with pytest.raises(ValueError):
        context.own_estimation
    context.process_global_pollster(global_pollster)
    assert context.global_estimation_exists
    assert context.estimation_source == "global"
    assert context.estimate_status == "single"
    assert context.estimation.expected == 1
    assert context.authoritative_record_consistent

    context.process_own_pollster(competing_pollster)
    assert context.estimation_source == "own"
    assert context.own_estimation_exists
    assert context.global_estimation_exists
    assert context.estimate_status == "contradictory"
    assert context.global_estimation.expected == 1
    assert context.own_estimation.expected == 2
    assert context.estimation.expected == 2
    assert not context.authoritative_record_consistent

    context.process_own_pollster(own_pollster)
    assert context.estimation_source == "global"
    assert context.estimate_status == "single"


def test_context_deal_with_defective_estimate():
    defective_estimate = data.EstimInput(1)
    defective_estimate.optimistic = 2
    poisoned_pollster = data.Pollster(get_independent_memory_io())
    poisoned_pollster.tell_points("task", defective_estimate)

    normal_pollster = data.Pollster(get_independent_memory_io())
    normal_pollster.tell_points("task", data.EstimInput(1))

    task = data.BaseCard("task")
    context = tm.Context(task)
    with pytest.raises(ValueError):
        context.process_own_pollster(poisoned_pollster)
    assert not context.own_estimation_exists
    assert context.estimation_source == "none"

    context.process_global_pollster(normal_pollster)
    assert context.estimation_source == "global"
    with pytest.raises(ValueError):
        context.process_global_pollster(poisoned_pollster)
    assert not context.global_estimation_exists
    assert context.estimation_source == "none"


def test_default_appdata():
    tm.AppData.CONFIG_BASENAME = "nothing here"
    appdata = tm.AppData.load()

    period = appdata.RETROSPECTIVE_PERIOD
    today = datetime.datetime.today()
    assert period[0] < today < period[1]
    assert (today - period[0]).days > 25
    assert (period[1] - today).days > 25
    assert period[0].day == 1
    assert period[1].day > 25
