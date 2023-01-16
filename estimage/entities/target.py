import re
import typing
import enum
import dataclasses

from .estimate import Estimate
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


@dataclasses.dataclass(init=False)
class BaseTarget:
    TIME_UNIT: str = None
    point_cost: float
    time_cost: float
    name: str
    title: str
    description: str
    dependents: typing.List["BaseTarget"]
    state: State
    collaborators: typing.List[str]
    tags: typing.Set[str]

    def __init__(self):
        self.point_cost = 0
        self.time_cost = 0
        self.name = ""
        self.title = ""
        self.description = ""
        self.dependents = []
        self.state = State.unknown
        self.collaborators = []
        self.tags = set()

    def as_class(self, cls):
        ret = cls()
        ret.TIME_UNIT = self.TIME_UNIT
        for fieldname in (
            "point_cost", "time_cost", "name", "title", "description", "state",
        ):
            setattr(ret, fieldname, getattr(self, fieldname))
        ret.dependents = [d.as_class(cls) for d in self.dependents]

        return ret

    def parse_point_cost(self, cost):
        return float(cost)

    def _convert_into_composition(self):
        ret = Composition(self.name)
        for d in self.dependents:
            if d.dependents:
                ret.add_composition(d._convert_into_composition())
            else:
                ret.add_element(d._convert_into_single_result())
        return ret

    def _convert_into_single_result(self):
        ret = TaskModel(self.name)
        if self.point_cost:
            ret.point_estimate = Estimate(self.point_cost, 0)
        if self.time_cost:
            ret.time_estimate = Estimate(self.time_cost, 0)
        if self.state in (State.abandoned, State.done):
            ret.mask()
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
        result = Composition("")
        if len(targets) == 1 and (target := targets[0]).dependents:
            result = target._convert_into_composition()
            return result
        for t in targets:
            if t.dependents:
                result.add_composition(t._convert_into_composition())
            else:
                result.add_element(t._convert_into_single_result())
        return result

    def get_tree(self):
        return self.to_tree([self])
