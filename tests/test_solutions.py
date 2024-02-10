import pytest

import estimage.solutions as tm
import estimage.problems as problems

import test_problems as ut
from test_problems import cards_one_two


@pytest.fixture
def solver():
    return tm.ProblemSolver()


def test_no_problem_no_solution(solver):
    assert len(solver.get_solutions([])) == 0


def test_basic_inconsistency_solution(solver, cards_one_two):
    card_one, card_two = cards_one_two
    card_two.point_cost = 2

    problem = ut.get_problem_of_cards(cards_one_two)
    solutions = solver.get_solutions([problem])
    assert len(solutions) == 1
    solution = solutions[0]
    assert solution.action == "update_points"
    assert solution.card_name == "one"
    solution.prime([card_one])
    # assert solution.end_value == card_two.point_cost


def test_update_children_inconsistency_solution(solver, cards_one_two):
    card_one, card_two = cards_one_two
    card_two.point_cost = 0
    card_three = tm.BaseCard("three")
    card_one.add_element(card_three)

    problem = ut.get_problem_of_cards(cards_one_two)
    solutions = solver.get_solutions([problem])
    assert len(solutions) == 1
    solution = solutions[0]
    assert solution.action == "update_children_points"
    assert solution.card_name == "one"
    solution.prime([card_one])
    assert solution.end_value == card_one.point_cost / 2.0


def test_update_complex_children_no_solution(solver, cards_one_two):
    card_one, card_two = cards_one_two
    card_three = problems.BaseCard("three")
    card_two.add_element(card_three)

    problem = ut.get_problem_of_cards([card_one])
    solutions = solver.get_solutions([problem])
    assert len(solutions) == 0
