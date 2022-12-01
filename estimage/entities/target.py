import re
import typing
import enum

from .task import TaskModel
from .composition import Composition
from .. import utilities


class State(enum.IntEnum):
    unknown = enum.auto()
    backlog = enum.auto()
    todo = enum.auto()
    in_progress = enum.auto()
    review = enum.auto()
    done = enum.auto()
    abandoned = enum.auto()


class BaseTarget:
    TIME_UNIT = None
    point_cost: float
    time_cost: float
    name: str
    title: str
    description: str
    dependents: typing.List["BaseTarget"]
    state: State

    def __init__(self):
        self.point_cost = 0
        self.time_cost = 0
        self.name = ""
        self.title = ""
        self.description = ""
        self.dependents = []
        self.state = State.unknown

    def parse_point_cost(self, cost):
        return float(cost)

    def _convert_into_composition(self):
        ret = Composition(self.name)
        for d in self.dependents:
            if d.dependents:
                ret.add_composition(d.get_tree())
            else:
                ret.add_element(d.get_tree())
        return ret

    def _convert_into_single_result(self):
        ret = TaskModel(self.name)
        if self.point_cost:
            ret.point_estimate.expected = self.point_cost
        if self.time_cost:
            ret.time_estimate.expected = self.time_cost
        return ret

    def get_tree(self) -> "Composition":
        if self.dependents:
            ret = self._convert_into_composition()
        else:
            ret = self._convert_into_single_result()
        return ret

    def add_element(self, what: "BaseTarget"):
        self.dependents.append(what)

    def parse_time_cost(self, cost):
        if not self.TIME_UNIT:
            raise RuntimeError("No time estimates are expected.")
        match = re.match(rf"([0-9.]+)\s*{self.TIME_UNIT}", cost)
        if match is None:
            raise ValueError(f"Couldn't parse cost {cost} in units {self.TIME_UNIT}")

        return float(match.groups()[0])

    def _load_point_cost(self) -> str:
        raise NotImplementedError()

    def _load_time_cost(self) -> str:
        raise NotImplementedError()

    def load_point_cost(self):
        cost_str = self._load_point_cost()
        self.point_cost = self.parse_point_cost(cost_str)

    def load_time_cost(self):
        cost_str = self._load_time_cost()
        self.time_cost = self.parse_time_cost(cost_str)

    def _save_point_cost(self, cost_str: str):
        raise NotImplementedError()

    def _save_time_cost(self, cost_str: str):
        raise NotImplementedError()

    def save_point_cost(self):
        cost = str(int(round(self.point_cost)))
        return self._save_point_cost(cost)

    def format_time_cost(self, cost):
        cost = int(round(cost))
        return f"{cost} {self.TIME_UNIT}"

    def save_time_cost(self):
        cost = self.format_time_cost(self.time_cost)
        return self._save_time_cost(cost)

    def save_metadata(self):
        raise NotImplementedError()

    def __contains__(self, lhs: "BaseTarget"):
        lhs_name = lhs.name

        if self.name == lhs.name:
            return True

        for rhs in self.dependents:
            if rhs.name == lhs_name:
                return True
            elif lhs in rhs:
                return True
        return False

    @classmethod
    def load_metadata(cls, name: str):
        raise NotImplementedError()

    @classmethod
    def to_tree(cls, targets: typing.List["BaseTarget"]):
        if not targets:
            return Composition("")
        targets = utilities.reduce_subsets_from_sets(targets)
        if len(targets) == 1:
            return targets[0].get_tree()
        result = Composition("")
        for t in targets:
            if t.dependents:
                result.add_composition(t.get_tree())
            else:
                result.add_element(t.get_tree())
        return result
