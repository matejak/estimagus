import dataclasses
import typing
import collections

import numpy as np

from .. import data
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
    def get_problem(cls, ** problem_data):
        tags = frozenset(problem_data.get("tags", set()))
        problem_data["tags"] = tags

        problem_tag = _get_problem_t_tags(tags)
        if not problem_tag:
            problem_t_final = cls
        else:
            problem_t_special = TAG_TO_PROBLEM_TYPE[problem_tag]
            problem_t_final = type("someProblem", (problem_t_special, cls), dict())
        return problem_t_final(** problem_data)


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

    def __init__(self, base_problem_t=Problem):
        self.model = None
        # ordered dictionary by ascending priority
        self.pollster_dict = None
        self.cards = []
        self.problems = []
        self.base_problem_t = base_problem_t

    def detect(self, model: EstiModel, cards: typing.Iterable[BaseCard], pollster_dict: typing.OrderedDict[str, data.Pollster]=None):
        self.model = model
        self.cards = cards
        self.pollster_dict = pollster_dict
        self._get_problems()
        return self.problems

    def _get_problems(self):
        for card in self.cards:
            self._get_card_problem(card)

    def _get_card_problem(self, card):
        computed_remaining_cost = self.model.remaining_point_estimate_of(card.name).expected
        computed_nominal_cost = self.model.nominal_point_estimate_of(card.name).expected
        analysis = Analysis(card, computed_remaining_cost, computed_nominal_cost)

        if self.card_consistent_by_definition(card):
            return

        if self.card_consistent_enough(analysis):
            return

        self._analyze_inconsistent_record(analysis)

    def _numbers_differ_significantly(self, lhs, rhs):
        if np.abs(lhs - rhs) > self.POINT_THRESHOLD:
            return True

    def _create_card_problem_data(self, card):
        problem_data = dict()
        problem_data["affected_card_name"] = card.name
        problem_data["tags"] = set()
        return problem_data

    def _card_is_not_estimated_but_has_children(self, card):
        return card.children and card.point_cost == 0

    def _card_has_no_children_with_children(self, card):
        for child in card.children:
            if child.children:
                return False
        return True

    def _inconsistent_card_missing_children_estimates(self, problem_data, analysis):
        card = analysis.card
        recorded_cost = analysis.recorded_cost
        problem_data["description_template"] = (
            "{formatted_task_name} "
            f"has inconsistent recorded point cost of {recorded_cost:.2g}, "
            f"as its children appear to lack estimations."
        )
        problem_data["tags"].add("missing_children_estimates")
        if self._card_has_no_children_with_children(card):
            problem_data["tags"].add("has_only_childless_children")

    def _inconsistent_card_differing_estimate(self, problem_data, analysis):
        card = analysis.card
        recorded_cost = analysis.recorded_cost
        if analysis.expected_computed_cost < analysis.recorded_cost:
            problem_data["tags"].add("sum_of_children_lower")
        if analysis.recorded_cost <= analysis.computed_nominal_cost:
            problem_data["tags"].add("estimate_within_nominal")
        problem_data["description_template"] = (
            "{formatted_task_name} "
            f"has inconsistent recorded point cost of {analysis.recorded_cost:.2g}, "
            f"while the deduced cost is {analysis.expected_computed_cost:.2g}"
        )
        problem_data["value_expected"] = analysis.expected_computed_cost

    def card_consistent_by_definition(self, card):
        return self._card_is_not_estimated_but_has_children(card)

    def card_consistent_enough(self, analysis):
        recorded_cost = analysis.recorded_cost
        expected_computed_cost = analysis.expected_computed_cost
        return not self._numbers_differ_significantly(recorded_cost, expected_computed_cost)

    def _analyze_inconsistent_record(self, analysis):
        card = analysis.card
        problem_data = self._create_card_problem_data(card)
        problem_data["tags"].add("inconsistent_estimate")
        problem_data["value_found"] = analysis.recorded_cost

        if card.children:
            self._analyze_inconsistent_record_of_subtree(problem_data, analysis)
        else:
            self._analyze_inconsistent_record_of_leaf(problem_data, analysis)

        problem_data["tags"] = frozenset(problem_data["tags"])
        self.problems.append(self.base_problem_t.get_problem(** problem_data))

    def _analyze_inconsistent_record_of_subtree(self, problem_data, analysis):
        if analysis.computed_nominal_cost == 0:
            self._inconsistent_card_missing_children_estimates(problem_data, analysis)
        else:
            self._inconsistent_card_differing_estimate(problem_data, analysis)

    def _pollster_is_fine(self, pollster, analysis):
        name = analysis.card.name
        if not pollster.knows_points(name):
            return True

        pollster_input = pollster.ask_points(name)
        pollster_expected = data.Estimate.from_input(pollster_input).expected
        if self._numbers_differ_significantly(analysis.recorded_cost, pollster_expected):
            return False

        return True

    def _analyze_leaf_wrt_pollsters(self, problem_data, analysis):
        pollster_names_by_priority_descending = reversed(self.pollster_dict.keys())
        for pollster_name in pollster_names_by_priority_descending:
            pollster = self.pollster_dict[pollster_name]

            if self._pollster_is_fine(pollster, analysis):
                continue

            problem_data["tags"].add("pollster_disagrees")
            problem_data["description_template"] = (
                "{formatted_task_name} "
                f"has recorded point cost of {analysis.recorded_cost:.2g}, "
                f"that is different from {analysis.expected_computed_cost:.2g}, "
                f"because the '{pollster_name}' Estimagus data supplies different value."
            )
            break

    def _analyze_inconsistent_record_of_leaf(self, problem_data, analysis):
        if self.pollster_dict:
            self._analyze_leaf_wrt_pollsters(problem_data, analysis)
