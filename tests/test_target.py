import datetime

import pytest

import estimage.data as tm
import estimage.entities.target as target
import estimage.inidata as tm_ini

from test_inidata import temp_filename, targetio_inifile_cls


@pytest.fixture
def leaf_target():
    ret = tm.BaseTarget("leaf")
    ret.point_cost = 4
    return ret


@pytest.fixture
def standalone_leaf_target():
    ret = tm.BaseTarget("feal")
    ret.point_cost = 2
    return ret


@pytest.fixture
def subtree_target(leaf_target):
    ret = tm.BaseTarget("subtree")
    ret.add_element(leaf_target)
    return ret


@pytest.fixture
def tree_target(subtree_target):
    ret = tm.BaseTarget("tree")
    ret.add_element(subtree_target)
    return ret


@pytest.fixture(params=("ini",))
def target_io(request, targetio_inifile_cls):
    choices = dict(
        ini=targetio_inifile_cls,
    )
    return choices[request.param]


def test_leaf_properties(leaf_target):
    result = leaf_target.to_tree([leaf_target]).elements[0]

    assert leaf_target.name == result.name
    assert leaf_target.point_cost == result.nominal_point_estimate.expected
    assert not result.masked


def test_finished_target_is_masked(leaf_target):
    done_states = (
        target.State.abandoned,
        target.State.done,
    )
    for state in done_states:
        leaf_target.state = state
        result = leaf_target.to_tree([leaf_target]).elements[0]
        assert result.masked


def test_subtree_properties(leaf_target, subtree_target, tree_target):
    assert subtree_target in subtree_target
    assert leaf_target in subtree_target
    assert subtree_target not in leaf_target
    assert leaf_target in tree_target

    composition = subtree_target.get_tree()
    assert subtree_target.name == composition.name
    assert len(composition.elements) == 1
    assert composition.elements[0].name == leaf_target.name

    assert leaf_target.point_cost == composition.nominal_point_estimate.expected


def test_tree_properties(leaf_target, subtree_target, tree_target):
    assert leaf_target in tree_target
    assert tree_target not in leaf_target
    composition = tree_target.get_tree()
    assert tree_target.name == composition.name
    assert subtree_target.name == composition.compositions[0].name
    assert leaf_target.name == composition.compositions[0].elements[0].name


def test_empty_target_to_tree():
    null_tree = tm.BaseTarget.to_tree([])
    assert null_tree == tm.Composition("")


def test_estimated_target_to_tree(leaf_target):
    simple_tree = leaf_target.get_tree()
    assert simple_tree.nominal_point_estimate.expected == leaf_target.point_cost
    assert simple_tree.nominal_point_estimate.sigma == 0
    assert simple_tree.nominal_point_estimate == tm.Estimate(leaf_target.point_cost, 0)


def test_leaf_target_to_tree(leaf_target, standalone_leaf_target):
    tree = tm.BaseTarget.to_tree([leaf_target])
    assert tree == leaf_target.get_tree()
    assert tree == tm.BaseTarget.to_tree([leaf_target, leaf_target])

    result = tm.Composition("")
    result.add_element(standalone_leaf_target.get_tree().elements[0])
    result.add_element(leaf_target.get_tree().elements[0])
    assert result == tm.BaseTarget.to_tree([standalone_leaf_target, leaf_target])


def test_estimated_tree_considers_only_leaf_cost(leaf_target, subtree_target):
    subtree_target.point_cost = 8
    composition = tm.BaseTarget.to_tree([leaf_target, subtree_target])
    assert composition.nominal_point_estimate.expected == leaf_target.point_cost


def test_tree_target_to_tree(leaf_target, standalone_leaf_target, subtree_target):
    result = tm.Composition("")
    result.add_composition(subtree_target.get_tree())
    result.add_element(standalone_leaf_target.get_tree().elements[0])
    assert result == tm.BaseTarget.to_tree([leaf_target, standalone_leaf_target, subtree_target])


def test_target_load_all(target_io):
    one = tm.BaseTarget("one")
    one.save_metadata(target_io)

    two = tm.BaseTarget("two")
    two.save_metadata(target_io)

    assert set(target_io.get_all_target_names()) == {"one", "two"}

    all_targets_by_id = target_io.get_loaded_targets_by_id()
    assert all_targets_by_id["one"].name == one.name


def fill_target_instance_with_stuff(t):
    t.point_cost = 5
    t.title = "Issue One"
    t.state = target.State.in_progress
    t.collaborators = ["a", "b"]
    t.assignee = "trubador"
    t.priority = 20
    t.loading_plugin = "estimage"
    t.tier = 1
    t.uri = "http://localhost/issue"
    t.status_summary = "Lorem Ipsum and So On"
    t.status_summary_time = datetime.datetime(1918, 8, 3)
    t.tags = ["t1", "l2", "t1"]
    t.work_span = (datetime.datetime(1939, 9, 1), datetime.datetime(1945, 5, 7))


def assert_targets_are_equal(lhs, rhs):
    assert lhs.name == rhs.name
    assert lhs.point_cost == rhs.point_cost
    assert lhs.title == rhs.title
    assert lhs.state == rhs.state
    assert lhs.collaborators == rhs.collaborators
    assert lhs.priority == rhs.priority
    assert lhs.status_summary == rhs.status_summary
    assert set(lhs.tags) == set(rhs.tags)
    assert lhs.work_span == rhs.work_span
    assert lhs.assignee == rhs.assignee
    assert lhs.status_summary_time == rhs.status_summary_time
    assert lhs.tier == rhs.tier
    assert lhs.loading_plugin == rhs.loading_plugin
    assert lhs.uri == rhs.uri


def test_target_load_and_save_values(target_io):
    one = tm.BaseTarget("one")
    fill_target_instance_with_stuff(one)
    one.save_metadata(target_io)

    all_targets_by_id = target_io.get_loaded_targets_by_id()
    loaded_one = all_targets_by_id["one"]
    loaded_one = loaded_one.load_metadata(loaded_one.name, target_io)
    assert_targets_are_equal(one, loaded_one)


def test_target_load_and_bulk_save(target_io):
    one = tm.BaseTarget("one")
    fill_target_instance_with_stuff(one)

    two = tm.BaseTarget("two")
    fill_target_instance_with_stuff(two)
    two.title = "Second t"
    two.tier = 6661

    target_io.bulk_save_metadata([one, two])

    all_targets_by_id = target_io.get_loaded_targets_by_id()
    loaded_one = all_targets_by_id["one"]
    assert_targets_are_equal(one, loaded_one)
    loaded_two = all_targets_by_id["two"]
    assert_targets_are_equal(two, loaded_two)
