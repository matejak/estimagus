import pytest

import estimage.data as tm
import estimage.entities.target as target
import estimage.inidata as tm_ini

from test_inidata import temp_filename


@pytest.fixture
def personweek_target():
    ret = tm.BaseTarget()
    ret.TIME_UNIT = "pw"
    return ret


@pytest.mark.dependency(name="basic_target")
def test_basic_target_properties(personweek_target):
    subject = personweek_target
    cost = subject.point_cost
    assert cost >= 0

    cost2 = subject.time_cost
    assert cost2 >= 0


@pytest.mark.dependency(depends=["basic_target"])
def test_target_value_parsing(personweek_target):
    subject = personweek_target
    assert subject.parse_point_cost("5") == 5

    subject.TIME_UNIT = "pw"
    assert subject.parse_time_cost("5pw") == 5
    assert subject.parse_time_cost("5 pw") == 5

    assert subject.format_time_cost(8.2) == "8 pw"

    subject.TIME_UNIT = "x"
    with pytest.raises(ValueError):
        subject.parse_time_cost("5pw")


@pytest.fixture
def leaf_target():
    ret = tm.BaseTarget()
    ret.name = "leaf"
    ret.point_cost = 4
    ret.time_cost = 3
    return ret


@pytest.fixture
def standalone_leaf_target():
    ret = tm.BaseTarget()
    ret.name = "feal"
    ret.point_cost = 2
    ret.time_cost = 1
    return ret


@pytest.fixture
def subtree_target(leaf_target):
    ret = tm.BaseTarget()
    ret.name = "subtree"
    ret.add_element(leaf_target)
    return ret


@pytest.fixture
def tree_target(subtree_target):
    ret = tm.BaseTarget()
    ret.name = "tree"
    ret.add_element(subtree_target)
    return ret


@pytest.fixture
def target_inifile(temp_filename):
    class TmpIniTarget(tm_ini.IniTarget):
        CONFIG_FILENAME = temp_filename

    yield TmpIniTarget


@pytest.fixture(params=("ini",))
def persistent_target_class(request, target_inifile):
    choices = dict(
        ini=target_inifile,
    )
    return choices[request.param]


def test_leaf_properties(leaf_target):
    result = leaf_target.to_tree([leaf_target]).elements[0]

    assert leaf_target.name == result.name
    assert leaf_target.point_cost == result.nominal_point_estimate.expected
    assert leaf_target.time_cost == result.nominal_time_estimate.expected
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
    assert leaf_target.time_cost == composition.nominal_time_estimate.expected


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

    assert simple_tree.nominal_time_estimate == tm.Estimate(leaf_target.time_cost, 0)


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
    subtree_target.time_cost = 7
    composition = tm.BaseTarget.to_tree([leaf_target, subtree_target])
    assert composition.nominal_point_estimate.expected == leaf_target.point_cost
    assert composition.nominal_time_estimate.expected == leaf_target.time_cost


def test_tree_target_to_tree(leaf_target, standalone_leaf_target, subtree_target):
    result = tm.Composition("")
    result.add_composition(subtree_target.get_tree())
    result.add_element(standalone_leaf_target.get_tree().elements[0])
    assert result == tm.BaseTarget.to_tree([leaf_target, standalone_leaf_target, subtree_target])


def test_target_load_all(persistent_target_class):
    one = persistent_target_class()
    one.name = "one"
    one.save_metadata()

    two = persistent_target_class()
    two.name = "two"
    two.save_metadata()

    assert set(persistent_target_class.get_all_target_names()) == {"one", "two"}

    all_targets_by_id = persistent_target_class.get_loaded_targets_by_id()
    assert all_targets_by_id["one"].name == one.name


def test_target_load_and_save_values(persistent_target_class):
    persistent_target_class.TIME_UNIT = "week"
    one = persistent_target_class()
    one.name = "one"
    one.point_cost = 5
    one.time_cost = 8
    one.save_point_cost()
    one.save_time_cost()
    one.title = "Issue One"
    one.state = target.State.in_progress
    one.collaborators = ["a", "b"]
    one.tags = ["t1", "l2", "t1"]
    one.save_metadata()

    all_targets_by_id = persistent_target_class.get_loaded_targets_by_id()
    loaded_one = all_targets_by_id["one"]
    loaded_one.load_point_cost()
    assert one.point_cost == loaded_one.point_cost
    loaded_one.load_time_cost()
    assert one.time_cost == loaded_one.time_cost
    loaded_one.load_metadata(loaded_one.name)
    assert loaded_one.title == one.title
    assert loaded_one.state == one.state
    assert loaded_one.collaborators == ["a", "b"]
    assert loaded_one.tags == set(["t1", "l2"])


def create_given_target_and_dependency(cls):
    bottom = cls()
    bottom.TIME_UNIT = "pw"
    bottom.name = "pwt"
    bottom.description = "desc"
    bottom.time_cost = 1.2
    bottom.state = tm.State.todo

    top = cls()
    top.TIME_UNIT = "pw"
    top.name = "PWT"
    top.description = "DESC"
    top.point_cost = 5.3
    top.add_element(bottom)
    top.state = tm.State.abandoned

    return top


def test_target_conversion():
    personweek_target = create_given_target_and_dependency(tm.BaseTarget)

    assert personweek_target == personweek_target

    assert personweek_target == personweek_target.as_class(tm.BaseTarget)

    personweek_ini_target = create_given_target_and_dependency(tm_ini.IniTarget)
    assert personweek_ini_target == personweek_target.as_class(tm_ini.IniTarget)
