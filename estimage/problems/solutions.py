import typing

from ..entities.card import BaseCard
from .problem import Problem


class Solution:
    card_name: str
    description: str = ""

    def __init__(self, problem: Problem):
        self.problem = problem

    def describe(self):
        return ""


class SolutionByUpdating(Solution):
    updates_model: bool

    def __init__(self, problem: Problem):
        super().__init__(problem)
        self.updates_model = True

    def describe(self):
        return f"Update the record of '{self.card_name}'"


class SolutionByUpdatingChildren(SolutionByUpdating):
    action = "update_children_points"
    description = "Update children of respective card, so the subtree is consistent"

    def describe(self):
        return f"Update children of '{self.card_name}', so they become consistent with the its record."


class SolutionByUpdatingSelf(SolutionByUpdating):
    action = "update_points"
    description = "Update the respective card, so it is consistent with its children"
    value: float

    def __init__(self, problem: Problem):
        super().__init__(problem)
        self.updates_model = False

    def describe(self):
        return f"Update the record of '{self.card_name}', so it matches records of its children."
