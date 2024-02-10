import dataclasses
import typing

from ..entities.card import BaseCard
from ..problems import Problem


@dataclasses.dataclass(init=False)
class Solution:
    card_name: str

    def __init__(self):
        self.card_name = ""

    def prime(self, cards: typing.Iterable[BaseCard]):
        raise NotImplementedError()


class SolutionByUpdating(Solution):
    end_value: float

    def __init__(self):
        super().__init__()
        self.end_value = None


class SolutionByUpdatingChildren(SolutionByUpdating):
    action = "update_children_points"

    def prime(self, cards: typing.Iterable[BaseCard]):
        my_card = [c for c in cards if c.name == self.card_name][0]
        self.end_value = my_card.point_cost / len(my_card.children)
        pass


class SolutionByUpdatingSelf(SolutionByUpdating):
    action = "update_points"

    def prime(self, cards: typing.Iterable[BaseCard]):
        pass


class ProblemSolver:
    SOLUTIONS = []

    def get_solutions(self, problems: typing.Iterable[Problem]):
        solutions = []
        for problem in problems:
            solution = self.get_solution_of(problem)
            if solution:
                solutions.append(solution)
        return solutions

    def get_solution_of(self, problem: Problem):
        for solution in self.SOLUTIONS:
            ret = solution(problem)
            if ret:
                return ret


def problem_solution(func):
    ProblemSolver.SOLUTIONS.append(func)
    return func


@problem_solution
def get_solution_of_inconsistent_parent(problem: Problem):
    if "inconsistent_estimate" not in problem.tags:
        return
    if "missing_estimates" in problem.tags:
        return
    ret = SolutionByUpdatingSelf()
    ret.card_name = problem.affected_cards_names[0]
    return ret


@problem_solution
def get_solution_of_inconsistent_children(problem: Problem):
    if "inconsistent_estimate" not in problem.tags:
        return
    if "missing_estimates" not in problem.tags:
        return
    if "childless_children" not in problem.tags:
        return

    ret = SolutionByUpdatingChildren()
    ret.card_name = problem.affected_cards_names[0]
    return ret
