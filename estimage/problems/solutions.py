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
    description = "Update children - divide the card's size evenly among them, so the subtree is consistent"
    solvable = True

    def describe(self):
        return f"Update children of '{self.card_name}', so they become consistent with the its record."

    def solve(self, card, synchro, io_cls):
        children_value = round(self.problem.value_found / len(card.children), 1)
        if children_value <= 0:
            return
        for c in card.children:
            synchro.set_tracker_points_of(c, children_value, io_cls)


class SolutionByUpdatingSelf(SolutionByUpdating):
    action = "update_points"
    description = "Update the respective card, so it is consistent"
    solvable = True

    def __init__(self, problem: Problem):
        super().__init__(problem)
        self.updates_model = False

    def describe(self):
        return f"Update the record of '{self.card_name}'."

    def solve(self, card, synchro, io_cls):
        synchro.set_tracker_points_of(card, self.problem.value_expected, io_cls)


class SolutionByUpdatingSelfDueTracker(SolutionByUpdatingSelf):
    description = "Update the respective card, so it is consistent with the Estimagus estimate"

    def describe(self):
        return f"Update the record of '{self.card_name}', so it matches the Estimagus estimate."


class SolutionByUpdatingSelfDueChildren(SolutionByUpdatingSelf):
    description = "Update the respective card, so it is consistent with its children"

    def describe(self):
        return f"Update the record of '{self.card_name}', so it matches records of its children."
