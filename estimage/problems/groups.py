import collections
import typing

from .problem import Problem
from . import solutions


class ProblemCategory:
    name: str = "generic"
    description: str = ""
    solution: solutions.Solution = None

    required_tags: typing.FrozenSet[str] = frozenset()
    unwanted_tags: typing.FrozenSet[str] = frozenset()

    def matches(self, p: Problem):
        if set(p.tags).intersection(self.required_tags) != self.required_tags:
            return False
        if set(p.tags).intersection(self.unwanted_tags):
            return False
        return True

    def _get_solution_of(self, p: Problem):
        return self.solution(p)

    def get_solution_of(self, p: Problem):
        if not self.solution:
            return None
        return self._get_solution_of(p)


class ProblemClassifier:
    CATEGORIES: typing.Mapping[str, ProblemCategory] = dict()
    classified_problems: typing.Mapping[str, typing.List[Problem]]
    _problems = typing.Mapping[Problem, str]

    def __init__(self):
        self.not_classified = []
        self.CATEGORIES = dict(** self.CATEGORIES)
        self.classified_problems = collections.defaultdict(list)
        self._problems = dict()

    def classify(self, problems: typing.Iterable[Problem]):
        for p in problems:
            self._classify_problem(p)

    def _classify_problem(self, problem: Problem):
        for c_name, c in self.CATEGORIES.items():
            if c.matches(problem):
                self.classified_problems[c_name].append(problem)
                self._problems[problem] = c_name
                return
        self.not_classified.append(problem)

    def get_category_of(self, problem: Problem):
        cat_name = self._problems.get(problem, None)
        return self.CATEGORIES.get(cat_name, ProblemCategory())

    def get_categories_with_problems(self):
        return [self.CATEGORIES[name] for name in self.classified_problems]

    def add_category(self, cat_type: typing.Type[ProblemCategory]):
        if (name := cat_type.name) in self.CATEGORIES:
            msg = f"Already have a category named '{name}'"
            raise KeyError(msg)
        self.CATEGORIES[name] = cat_type()


def problem_category(cls):
    ProblemClassifier.CATEGORIES[cls.name] = cls()
    return cls


@problem_category
class ReasonableOutdated(ProblemCategory):
    name = "reasonable_outdated"
    description = "Estimate is inconsistent with children, but lower than the nominal size and greater than the size of tasks not yet completed."
    solution = solutions.SolutionByUpdatingSelf

    required_tags = frozenset([
        "inconsistent_estimate",
        "estimate_within_nominal",
        "sum_of_children_lower",
    ])
    unwanted_tags = frozenset([
        "missing_children_estimates",
    ])


@problem_category
class UnestimatedChildren(ProblemCategory):
    name = "unestimated_children"
    description = "Children have no size estimated, but the parent issue has."
    solution = solutions.SolutionByUpdatingChildren

    required_tags = set([
        "inconsistent_estimate",
        "missing_children_estimates",
        "has_only_childless_children",
    ])


@problem_category
class GenericInconsistent(ProblemCategory):
    name = "generic_inconsistent"
    solution = solutions.SolutionByUpdatingSelf

    required_tags = frozenset(["inconsistent_estimate"])
    unwanted_tags = frozenset(["missing_estimates"])
