import pytest

from estimage.problems import problem
import estimage.plugins.redhat_compliance as tm

from tests.test_problems import cards_one_two


def get_problem_of_cards(cards):
    model = problem.EstiModel()
    comp = cards[0].to_tree(cards)
    model.use_composition(comp)
    problems = tm.ProblemDetector().detect(model, cards)
    assert len(problems) == 1
    return problems[0]


def test_zero_tasks_also_inconsistent(cards_one_two):
    one, two = cards_one_two
    one.point_cost = 0
    problem = get_problem_of_cards(cards_one_two)
    assert "inconsistent_estimate" in problem.tags
    assert "unestimated_parent" in problem.tags

    one.point_cost = two.point_cost + 1
    problem = get_problem_of_cards(cards_one_two)
    assert "inconsistent_estimate" in problem.tags
    assert "unestimated_parent" not in problem.tags
