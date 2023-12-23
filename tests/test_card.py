import datetime

import pytest

import estimage.data as tm
import estimage.entities.card as card
from estimage.persistence.card import memory

from tests.test_inidata import temp_filename, cardio_inifile_cls


@pytest.fixture
def leaf_card():
    ret = tm.BaseCard("leaf")
    ret.point_cost = 4
    return ret


@pytest.fixture
def standalone_leaf_card():
    ret = tm.BaseCard("feal")
    ret.point_cost = 2
    return ret


@pytest.fixture
def subtree_card(leaf_card):
    ret = tm.BaseCard("subtree")
    ret.add_element(leaf_card)
    return ret


@pytest.fixture
def tree_card(subtree_card):
    ret = tm.BaseCard("tree")
    ret.add_element(subtree_card)
    return ret


@pytest.fixture(params=("ini", "memory"))
def card_io(request, cardio_inifile_cls):
    choices = dict(
        ini=cardio_inifile_cls,
        memory=memory.MemoryCardIO,
    )
    io = choices[request.param]
    io.forget_all()
    yield io
    io.forget_all()


def test_leaf_properties(leaf_card):
    result = leaf_card.to_tree([leaf_card]).elements[0]

    assert leaf_card.name == result.name
    assert leaf_card.point_cost == result.nominal_point_estimate.expected
    assert not result.masked


def test_finished_card_is_masked(leaf_card):
    done_states = (
        card.STATUSES.get("abandoned"),
        card.STATUSES.get("done"),
    )
    for state in done_states:
        leaf_card.status = state
        result = leaf_card.to_tree([leaf_card]).elements[0]
        assert result.masked


def test_subtree_properties(leaf_card, subtree_card, tree_card):
    assert subtree_card in subtree_card
    assert leaf_card in subtree_card
    assert leaf_card.parent is subtree_card
    assert subtree_card not in leaf_card
    assert leaf_card in tree_card
    assert subtree_card.parent is tree_card
    assert not tree_card.parent

    composition = subtree_card.get_tree()
    assert subtree_card.name == composition.name
    assert len(composition.elements) == 1
    assert composition.elements[0].name == leaf_card.name

    assert leaf_card.point_cost == composition.nominal_point_estimate.expected


def test_tree_properties(leaf_card, subtree_card, tree_card):
    assert leaf_card in tree_card
    assert tree_card not in leaf_card
    composition = tree_card.get_tree()
    assert tree_card.name == composition.name
    assert subtree_card.name == composition.compositions[0].name
    assert leaf_card.name == composition.compositions[0].elements[0].name


def test_empty_card_to_tree():
    null_tree = tm.BaseCard.to_tree([])
    assert null_tree == tm.Composition("")


def test_estimated_card_to_tree(leaf_card):
    simple_tree = leaf_card.get_tree()
    assert simple_tree.nominal_point_estimate.expected == leaf_card.point_cost
    assert simple_tree.nominal_point_estimate.sigma == 0
    assert simple_tree.nominal_point_estimate == tm.Estimate(leaf_card.point_cost, 0)


def test_leaf_card_to_tree(leaf_card, standalone_leaf_card):
    tree = tm.BaseCard.to_tree([leaf_card])
    assert tree == leaf_card.get_tree()
    assert tree == tm.BaseCard.to_tree([leaf_card, leaf_card])

    result = tm.Composition("")
    result.add_element(standalone_leaf_card.get_tree().elements[0])
    result.add_element(leaf_card.get_tree().elements[0])
    assert result == tm.BaseCard.to_tree([standalone_leaf_card, leaf_card])


def test_estimated_tree_considers_only_leaf_cost(leaf_card, subtree_card):
    subtree_card.point_cost = 8
    composition = tm.BaseCard.to_tree([leaf_card, subtree_card])
    assert composition.nominal_point_estimate.expected == leaf_card.point_cost


def test_tree_card_to_tree(leaf_card, standalone_leaf_card, subtree_card):
    result = tm.Composition("")
    result.add_composition(subtree_card.get_tree())
    result.add_element(standalone_leaf_card.get_tree().elements[0])
    assert result == tm.BaseCard.to_tree([leaf_card, standalone_leaf_card, subtree_card])


def test_card_load_all(card_io):
    one = tm.BaseCard("one")
    one.save_metadata(card_io)

    two = tm.BaseCard("two")
    two.save_metadata(card_io)

    assert set(card_io.get_all_card_names()) == {"one", "two"}

    all_cards_by_id = card_io.get_loaded_cards_by_id()
    assert all_cards_by_id["one"].name == one.name


def fill_card_instance_with_stuff(t):
    t.point_cost = 5
    t.title = "Issue One"
    t.status = card.STATUSES.get("in_progress")
    t.collaborators = ["a", "b"]
    t.assignee = "trubador"
    t.priority = 20
    t.loading_plugin = "estimage"
    t.tier = 1
    t.uri = "http://localhost/issue"
    t.tags = ["t1", "l2", "t1"]
    t.work_span = (datetime.datetime(1939, 9, 1), datetime.datetime(1945, 5, 7))


def assert_cards_are_equal(lhs, rhs):
    assert lhs.name == rhs.name
    assert lhs.point_cost == rhs.point_cost
    assert lhs.title == rhs.title
    assert lhs.status == rhs.state
    assert lhs.collaborators == rhs.collaborators
    assert lhs.priority == rhs.priority
    assert set(lhs.tags) == set(rhs.tags)
    assert lhs.work_span == rhs.work_span
    assert lhs.assignee == rhs.assignee
    assert lhs.tier == rhs.tier
    assert lhs.loading_plugin == rhs.loading_plugin
    assert lhs.uri == rhs.uri


def base_card_load_save(card_io, cls, filler, tester):
    one = cls("one")
    filler(one)
    one.save_metadata(card_io)

    all_cards_by_id = card_io.get_loaded_cards_by_id(cls)
    loaded_one = all_cards_by_id["one"]
    tester(one, loaded_one)

    loaded_one = cls.load_metadata("one", card_io)
    tester(one, loaded_one)


def test_card_load_and_save_values(card_io):
    base_card_load_save(card_io, tm.BaseCard, fill_card_instance_with_stuff, assert_cards_are_equal)


def test_card_load_and_bulk_save(card_io):
    one = tm.BaseCard("one")
    fill_card_instance_with_stuff(one)

    two = tm.BaseCard("two")
    fill_card_instance_with_stuff(two)
    two.title = "Second t"
    two.tier = 6661

    card_io.bulk_save_metadata([one, two])

    all_cards_by_id = card_io.get_loaded_cards_by_id()
    loaded_one = all_cards_by_id["one"]
    assert_cards_are_equal(one, loaded_one)
    loaded_two = all_cards_by_id["two"]
    assert_cards_are_equal(two, loaded_two)


def test_card_forget(card_io):
    card_io.forget_all()

    one = tm.BaseCard("one")
    one.save_metadata(card_io)
    card_io.forget_all()
    assert not card_io.load_all_cards()
