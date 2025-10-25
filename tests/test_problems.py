import pytest

import collections

import estimage.data as data
import estimage.persistence
import estimage.problems.problem as tm


@pytest.fixture
def cards_one_two():
    card_two = tm.BaseCard("two")
    card_two.status = "todo"
    card_two.point_cost = 1

    card_one = tm.BaseCard("one")
    card_one.status = "todo"
    card_one.point_cost = 1
    card_one.add_element(card_two)
    return [card_one, card_two]


def test_model_picks_no_problem():
    card_one = tm.BaseCard("one")
    card_one.status = "todo"
    card_one.point_cost = 1

    problems = get_problems_of_cards([card_one])
    assert len(problems) == 0


def get_problems_of_cards(cards, pollster_dict=None):
    model = tm.EstiModel()
    comp = cards[0].to_tree(cards)
    model.use_composition(comp)
    if pollster_dict:
        for pollster in pollster_dict.values():
            pollster.supply_valid_estimations_to_tasks(model.get_all_task_models())
    problems = tm.ProblemDetector()
    problems.detect(model, cards, pollster_dict)
    return problems.problems


def get_problem_of_cards(cards):
    problems = get_problems_of_cards(cards)
    assert len(problems) == 1
    return problems[0]


def test_model_finds_no_problem(cards_one_two):
    assert len(get_problems_of_cards(cards_one_two)) == 0


def test_model_tolerates_no_estimate_of_parent(cards_one_two):
    card_one, card_two = cards_one_two
    card_one.point_cost = 0
    assert len(get_problems_of_cards(cards_one_two)) == 0


def test_model_tolerates_small_inconsistency(cards_one_two):
    card_one, card_two = cards_one_two
    card_two.point_cost = 1.2
    assert len(get_problems_of_cards(cards_one_two)) == 0


def test_model_notices_basic_inconsistency(cards_one_two):
    card_one, card_two = cards_one_two
    card_two.point_cost = 2
    problem = get_problem_of_cards(cards_one_two)
    assert "inconsistent_estimate" in problem.tags
    assert "sum_of_children_lower" not in problem.tags
    assert "one" in problem.description
    assert problem.affected_card_name == "one"
    assert problem.value_expected == 2
    assert problem.value_found == 1
    assert "2" in problem.description
    assert "of 1" in problem.description


def test_model_notices_inconsistency_unlikely_caused_by_progress(cards_one_two):
    card_one, card_two = cards_one_two
    card_two.point_cost = 0.5
    problem = get_problem_of_cards(cards_one_two)
    assert "inconsistent_estimate" in problem.tags
    assert "sum_of_children_lower" in problem.tags
    assert not "estimate_within_nominal" in problem.tags
    assert problem.value_expected == 0.5
    assert problem.value_found == 1


def test_model_notices_inconsistency_probably_caused_by_progress(cards_one_two):
    card_one, card_two = cards_one_two
    card_two.status = "done"
    problem = get_problem_of_cards(cards_one_two)
    assert "inconsistent_estimate" in problem.tags
    assert "sum_of_children_lower" in problem.tags
    assert "estimate_within_nominal" in problem.tags
    assert problem.value_expected == 0
    assert problem.value_found == 1


def test_model_notices_children_not_estimated(cards_one_two):
    card_one, card_two = cards_one_two

    card_two.status = "done"
    problem = get_problem_of_cards(cards_one_two)
    assert "inconsistent_estimate" in problem.tags
    assert "missing_children_estimates" not in problem.tags
    assert "one" in problem.description
    assert "not estimated" not in problem.description
    assert problem.value_expected == 0
    assert problem.value_found == 1

    card_two.point_cost = 0
    problem = get_problem_of_cards(cards_one_two)
    assert "one" in problem.description
    assert "inconsistent_estimate" in problem.tags
    assert "missing_children_estimates" in problem.tags
    assert problem.value_expected is None
    assert problem.value_found == 1


def test_model_finds_status_problem(cards_one_two):
    card_one, card_two = cards_one_two
    card_two.status = "done"
    problems = get_problems_of_cards([card_two])
    assert len(problems) == 0

    card_two.point_cost = card_one.point_cost
    problem = get_problem_of_cards(cards_one_two)
    assert "one" == problem.affected_card_name


def test_model_finds_estimation_problem(cards_one_two):
    memory_pollster_io = estimage.persistence.get_persistence(data.Pollster, "memory")
    card_one, card_two = cards_one_two
    pollster = data.Pollster(io_cls=memory_pollster_io)
    pollster.tell_points(card_two.name, data.EstimInput(card_two.point_cost + 1))
    problems = get_problems_of_cards([card_two], collections.OrderedDict(low_prio=pollster))
    assert len(problems) == 1
    problem = problems[0]
    assert "pollster_disagrees" in problem.tags

    pollster.tell_points(card_two.name, data.EstimInput(card_two.point_cost))
    problems = get_problems_of_cards([card_two], collections.OrderedDict(low_prio=pollster))
    assert len(problems) == 0

    # The wrong pollster gets picked up if another one is OK
    pollster_two = data.Pollster(io_cls=memory_pollster_io)
    pollster_two.set_namespace("p2")
    pollster_two.tell_points(card_two.name, data.EstimInput(card_two.point_cost + 1))
    problems = get_problems_of_cards([card_two], collections.OrderedDict(low_prio=pollster, high_prio=pollster_two))
    assert len(problems) == 1
    problem = problems[0]
    assert "pollster_disagrees" in problem.tags
    assert "high_prio" in problem.description

    # Even if both pollsters are wrong, the one that matters is identified correcly
    problems = get_problems_of_cards([card_two], collections.OrderedDict(low_prio=pollster_two, high_prio=pollster_two))
    assert len(problems) == 1
    problem = problems[0]
    assert "pollster_disagrees" in problem.tags
    assert "high_prio" in problem.description
