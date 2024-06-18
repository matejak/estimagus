import dataclasses
import typing
import collections

import numpy as np

from ..entities.card import BaseCard
from ..entities.model import EstiModel
from .. import PluginResolver


TAG_TO_PROBLEM_TYPE = dict()

def _get_problem_t_tags(tags):
    problem_tags = list(tags.intersection(set(TAG_TO_PROBLEM_TYPE.keys())))
    if not problem_tags:
        return ""
    return problem_tags[0]


def problem_associated_with_tag(tag):
    def wrapper(wrapped):
        TAG_TO_PROBLEM_TYPE[tag] = wrapped
        return wrapped
    return wrapper


@dataclasses.dataclass(frozen=True)
class Problem:
    description_template: str = ""
    affected_card_name: str = ""
    tags: typing.FrozenSet[str] = frozenset()

    def get_formatted_description(self, formatted_task_name):
        return self.description_template.format(formatted_task_name=formatted_task_name)

    def format_task_name(self):
        return f"'{self.affected_card_name}'"

    @property
    def description(self):
        return self.description_template.format(formatted_task_name=self.format_task_name())

    @classmethod
    def get_problem(cls, ** data):
        tags = frozenset(data.get("tags", set()))
        data["tags"] = tags

        problem_tag = _get_problem_t_tags(tags)
        if not problem_tag:
            problem_t_final = cls
        else:
            problem_t_special = TAG_TO_PROBLEM_TYPE[problem_tag]
            problem_t_final = type("someProblem", (problem_t_special, cls), dict())
        return problem_t_final(** data)


@problem_associated_with_tag("inconsistent_estimate")
@dataclasses.dataclass(frozen=True)
class ValueProblem(Problem):
    value_expected: float = None
    value_found: float = None


class Analysis:
    card: BaseCard
    recorded_cost: float
    computed_nominal_cost: float
    expected_computed_cost: float

    def __init__(self, card, computed_remaining_cost, computed_nominal_cost):
        self.card = card
        self.recorded_cost = card.point_cost
        self.computed_nominal_cost = computed_nominal_cost

        self.expected_computed_cost = computed_nominal_cost
        if card.children:
            self.expected_computed_cost = computed_remaining_cost


@PluginResolver.class_is_extendable("ProblemDetector")
class ProblemDetector:
    POINT_THRESHOLD = 0.4

    def __init__(self, model: EstiModel, cards: typing.Iterable[BaseCard], base_problem_t=Problem):
        self.model = model
        self.cards = cards
        self.problems = []
        self.base_problem_t = base_problem_t

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

    def _treat_inconsistent_estimate(self, analysis: Analysis):
        card = analysis.card
        data = self._create_card_problem_data(card)
        data["tags"].add("inconsistent_estimate")
        data["value_found"] = analysis.recorded_cost
        if analysis.computed_nominal_cost == 0:
            self._inconsistent_card_missing_children_estimates(data, card)
        else:
            self._inconsistent_card_differing_estimate(data, card, analysis)
        data["tags"] = frozenset(data["tags"])
        self.problems.append(self.base_problem_t.get_problem(** data))

    def _card_has_no_children_with_children(self, card):
        for child in card.children:
            if child.children:
                return False
        return True

    def _inconsistent_card_missing_children_estimates(self, data, card):
        recorded_cost = data['value_found']
        data["description_template"] = (
            "{formatted_task_name} "
            f"has inconsistent recorded point cost of {recorded_cost:.2g}, "
            f"as its children appear to lack estimations."
        )
        data["tags"].add("missing_children_estimates")
        if self._card_has_no_children_with_children(card):
            data["tags"].add("has_only_childless_children")

    def _inconsistent_card_differing_estimate(self, data, card, analysis):
        recorded_cost = data['value_found']
        if analysis.expected_computed_cost < analysis.recorded_cost:
            data["tags"].add("sum_of_children_lower")
        if analysis.recorded_cost <= analysis.computed_nominal_cost:
            data["tags"].add("estimate_within_nominal")
        data["description_template"] = (
            "{formatted_task_name} "
            f"has inconsistent recorded point cost of {analysis.recorded_cost:.2g}, "
            f"while the deduced cost is {analysis.expected_computed_cost:.2g}"
        )
        data["value_expected"] = analysis.expected_computed_cost

    def card_consistent_by_definition(self, card):
        return self._card_is_not_estimated_but_has_children(card)

    def card_consistent_enough(self, recorded_cost, expected_computed_cost):
        return not self._numbers_differ_significantly(recorded_cost, expected_computed_cost)

    def _analyze_inconsistent_record(self, card):
        recorded_cost = card.point_cost

        computed_remaining_cost = self.model.remaining_point_estimate_of(card.name).expected
        computed_nominal_cost = self.model.nominal_point_estimate_of(card.name).expected
        analysis = Analysis(card, computed_remaining_cost, computed_nominal_cost)

        if self.card_consistent_by_definition(card):
            return

        if self.card_consistent_enough(recorded_cost, analysis.expected_computed_cost):
            return

        self._treat_inconsistent_estimate(analysis)
