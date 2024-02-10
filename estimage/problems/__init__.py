import dataclasses
import typing

import numpy as np

from ..entities.card import BaseCard
from ..entities.model import EstiModel


@dataclasses.dataclass(init=False)
class Problem:
    description: str
    affected_cards_names: list[str]
    tags: set[str]

    def __init__(self):
        self.description = ""
        self.affected_cards_names = []
        self.tags = frozenset()

    def add_tag(self, tag):
        self.tags = frozenset(self.tags.union([tag]))


class ProblemDetector:
    POINT_THRESHOLD = 0.4

    def __init__(self, model: EstiModel, cards: typing.Iterable[BaseCard]):
        self.model = model
        self.cards = cards
        self.problems = []

        self._get_problems()

    def _get_problems(self):
        for card in self.cards:
            self._get_card_problem(card)

    def _get_card_problem(self, card):
        self._analyze_inconsistent_record(card)

    def _numbers_differ_significantly(self, lhs, rhs):
        if np.abs(lhs - rhs) > self.POINT_THRESHOLD:
            return True

    def _create_and_add_card_problem(self, card):
        problem = Problem()
        problem.affected_cards_names.append(card.name)
        self.problems.append(problem)
        return problem

    def _card_is_not_estimated_but_has_children(self, card):
        return card.children and card.point_cost == 0

    def _treat_inconsistent_estimate(self, card, computed_nominal_cost, recorded_cost, expected_computed_cost):
        problem = self._create_and_add_card_problem(card)
        problem.add_tag("inconsistent_estimate")
        if computed_nominal_cost == 0:
            self._inconsistent_card_missing_estimates(problem, card, recorded_cost)
        else:
            self._inconsistent_card_differing_estimate(problem, card, recorded_cost, expected_computed_cost)

    def _card_has_no_children_with_children(self, card):
        for child in card.children:
            if child.children:
                return False
        return True

    def _inconsistent_card_missing_estimates(self, problem, card, recorded_cost):
        problem.description = (
            f"'{card.name}' has inconsistent recorded point cost of {recorded_cost:.2g}, "
            f"as its children appear to lack estimations."
        )
        problem.add_tag("missing_estimates")
        if self._card_has_no_children_with_children(card):
            problem.add_tag("childless_children")

    def _inconsistent_card_differing_estimate(self, problem, card, recorded_cost, expected_computed_cost):
        if expected_computed_cost < recorded_cost:
            problem.add_tag("sum_of_children_lower")
        problem.description = (
            f"'{card.name}' has inconsistent recorded point cost of {recorded_cost:.2g}, "
            f"while the deduced cost is {expected_computed_cost:.2g}"
        )

    def _analyze_inconsistent_record(self, card):
        recorded_cost = card.point_cost
        computed_remaining_cost = self.model.remaining_point_estimate_of(card.name).expected
        computed_nominal_cost = self.model.nominal_point_estimate_of(card.name).expected
        expected_computed_cost = computed_nominal_cost
        if card.children:
            expected_computed_cost = computed_remaining_cost

        if self._card_is_not_estimated_but_has_children(card):
            return

        if not self._numbers_differ_significantly(recorded_cost, expected_computed_cost):
            return

        self._treat_inconsistent_estimate(card, computed_nominal_cost, recorded_cost, expected_computed_cost)
