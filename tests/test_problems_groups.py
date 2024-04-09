import pytest

import estimage.problems.groups as tm

import test_problems
from test_problems import cards_one_two


def test_problem_categories_trivial():
    dumb_classifier = tm.ProblemClassifier()
    p = tm.Problem.get_problem(tags=["unspecific"])
    dumb_classifier.classify([p])
    others = dumb_classifier.not_classified
    assert len(others) == 1
    assert others[0] == p


class CustomClassifier(tm.ProblemClassifier):
    pass


@pytest.fixture
def classifier():
    return CustomClassifier()


class Underestimation(tm.ProblemCategory):
    name = "underestimation"

    def matches(self, p):
        return "underestimated" in p.tags


def test_problem_category_match():
    cat = Underestimation()
    p = tm.Problem(tags=["underestimated"])
    assert cat.matches(p)

    bad_p = tm.Problem(tags=["nothing"])
    assert not cat.matches(bad_p)


def test_problem_categories_no_duplication(classifier):
    classifier.add_category(Underestimation)
    with pytest.raises(KeyError):
        classifier.add_category(Underestimation)


def test_problem_categories_basic(classifier):
    classifier.add_category(Underestimation)
    p = tm.Problem.get_problem(tags=["underestimated"])
    classifier.classify([p])
    assert not classifier.not_classified
    underestimation_problems = classifier.classified_problems["underestimation"]
    underestimation_problems = list(underestimation_problems.values())
    assert underestimation_problems[0] == p


def test_basic_inconsistency_solution(classifier, cards_one_two):
    card_one, card_two = cards_one_two
    card_two.point_cost = 2

    problem = test_problems.get_problem_of_cards(cards_one_two)
    classifier.classify([problem])
    problem_category = classifier.get_category_of(problem)
    assert problem_category.name == "generic_inconsistent"
    solution_type = problem_category.solution
    assert solution_type.action == "update_points"
    assert "Update the respective card" in solution_type.description
    solution = problem_category.get_solution_of(problem)
    assert solution.problem.affected_card_name == "one"
    assert solution.updates_model == False

    only_category = classifier.get_categories_with_problems()[0]
    assert only_category.name == problem_category.name
