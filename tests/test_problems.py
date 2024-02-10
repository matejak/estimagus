import pytest

import estimage.problems as tm


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


def get_problems_of_cards(cards):
    model = tm.EstiModel()
    comp = cards[0].to_tree(cards)
    model.use_composition(comp)
    problems = tm.ProblemDetector(model, cards)
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
    assert "is 2" in problem.description
    assert "of 1" in problem.description


def test_model_notices_inconsistency_maybe_caused_by_progress(cards_one_two):
    card_one, card_two = cards_one_two
    card_two.point_cost = 0.5
    problem = get_problem_of_cards(cards_one_two)
    assert "inconsistent_estimate" in problem.tags
    assert "sum_of_children_lower" in problem.tags


def test_model_notices_children_not_estimated(cards_one_two):
    card_one, card_two = cards_one_two

    card_two.status = "done"
    problem = get_problem_of_cards(cards_one_two)
    assert "inconsistent_estimate" in problem.tags
    assert "missing_estimates" not in problem.tags
    assert "one" in problem.description
    assert "not estimated" not in problem.description

    card_two.point_cost = 0
    problem = get_problem_of_cards(cards_one_two)
    assert "one" in problem.description
    assert "inconsistent_estimate" in problem.tags
    assert "missing_estimates" in problem.tags


def test_model_finds_status_problem(cards_one_two):
    card_one, card_two = cards_one_two
    card_two.status = "done"
    problems = get_problems_of_cards([card_two])
    assert len(problems) == 0

    card_two.point_cost = card_one.point_cost
    problem = get_problem_of_cards(cards_one_two)
    assert "one" in problem.affected_cards_names
