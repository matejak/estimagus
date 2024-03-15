import dataclasses
import typing
import collections

import numpy as np

from ..entities.card import BaseCard
from ..entities.model import EstiModel


TAG_TO_PROBLEM_TYPE = dict()

def get_problem(** data):
    data["tags"] = frozenset(data.get("tags", frozenset()))
    problem_tags = list(data["tags"].intersection(set(TAG_TO_PROBLEM_TYPE.keys())))
    if not problem_tags:
        return Problem(** data)
    return TAG_TO_PROBLEM_TYPE[problem_tags[0]](** data)


def problem_associated_with_tag(tag):
    def wrapper(wrapped):
        TAG_TO_PROBLEM_TYPE[tag] = wrapped
        return wrapped
    return wrapper


@dataclasses.dataclass(frozen=True)
class Problem:
    description: str = ""
    affected_card_name: str = ""
    tags: typing.FrozenSet[str] = frozenset()

    def format_task_name(self):
        return self.affected_card_name


@problem_associated_with_tag("inconsistent_estimate")
@dataclasses.dataclass(frozen=True)
class ValueProblem(Problem):
    value_expected: float = None
    value_found: float = None


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

    def _create_card_problem_data(self, card):
        data = dict()
        data["affected_card_name"] = card.name
        data["tags"] = set()
        return data

    def _card_is_not_estimated_but_has_children(self, card):
        return card.children and card.point_cost == 0

    def _treat_inconsistent_estimate(self, card, computed_nominal_cost, recorded_cost, expected_computed_cost):
        data = self._create_card_problem_data(card)
        data["tags"].add("inconsistent_estimate")
        data["value_found"] = recorded_cost
        if computed_nominal_cost == 0:
            self._inconsistent_card_missing_children_estimates(data, card)
        else:
            self._inconsistent_card_differing_estimate(data, card, expected_computed_cost, computed_nominal_cost)
        data["tags"] = frozenset(data["tags"])
        self.problems.append(get_problem(** data))

    def _card_has_no_children_with_children(self, card):
        for child in card.children:
            if child.children:
                return False
        return True

    def _inconsistent_card_missing_children_estimates(self, data, card):
        recorded_cost = data['value_found']
        data["description"] = (
            f"'{card.name}' has inconsistent recorded point cost of {recorded_cost:.2g}, "
            f"as its children appear to lack estimations."
        )
        data["tags"].add("missing_children_estimates")
        if self._card_has_no_children_with_children(card):
            data["tags"].add("has_only_childless_children")

    def _inconsistent_card_differing_estimate(self, data, card, expected_computed_cost, computed_nominal_cost):
        recorded_cost = data['value_found']
        if expected_computed_cost < recorded_cost:
            data["tags"].add("sum_of_children_lower")
        if recorded_cost <= computed_nominal_cost:
            data["tags"].add("estimate_within_nominal")
        data["description"] = (
            f"'{card.name}' has inconsistent recorded point cost of {recorded_cost:.2g}, "
            f"while the deduced cost is {expected_computed_cost:.2g}"
        )
        data["value_expected"] = expected_computed_cost

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

