import typing

from ..entities.card import BaseCard
from .problem import Problem


class Solution:
    card_name: str
    problem: Problem
    description: str = ""

    def __init__(self, problem: Problem):
        self.problem = problem

    def describe(self):
        return ""

    def solve(self, card, synchro, io_cls):
        raise NotImplementedError


class SolutionByUpdating(Solution):
    updates_model: bool
    solvable = False

    def __init__(self, problem: Problem):
        super().__init__(problem)
        self.updates_model = True

    def describe(self):
        return f"Update the record of '{self.card_name}'"


class SolutionByUpdatingChildren(SolutionByUpdating):
    action = "update_children_points"
    description = "Update divide the card's size among its children, so the subtree is consistent"

    def describe(self):
        return f"Update children of '{self.card_name}', so they become consistent with the its record."


class SolutionByUpdatingSelf(SolutionByUpdating):
    action = "update_points"
    description = "Update the respective card, so it is consistent with its children"
    solvable = True
    value: float

    def __init__(self, problem: Problem):
        super().__init__(problem)
        self.updates_model = False

    def describe(self):
        return f"Update the record of '{self.card_name}', so it matches records of its children."

    def solve(self, card, synchro, io_cls):
        synchro.set_tracker_points_of(card, self.problem.value_expected, io_cls)
