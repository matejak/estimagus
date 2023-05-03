import re
import typing
import enum
import dataclasses
import datetime

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
    point_cost: float
    time_cost: float
    name: str
    title: str
    description: str
    dependents: typing.List["BaseTarget"]
    state: State
    collaborators: typing.List[str]
    assignee: str
    priority: float
    status_summary: str
    status_summary_time: datetime.datetime
    tags: typing.Set[str]
    work_span: typing.Tuple[datetime.datetime, datetime.datetime]
    tier: int
    uri: str
    loading_plugin: str

    def __init__(self):
        self.point_cost = 0
        self.time_cost = 0
        self.name = ""
        self.title = ""
        self.description = ""
        self.dependents = []
        self.state = State.unknown
        self.collaborators = []
        self.assignee = ""
        self.priority = 50.0
        self.status_summary = ""
        self.status_summary_time = None
        self.tags = set()
        self.work_span = None
        self.tier = 0
        self.uri = ""
        self.loading_plugin = ""

    def as_class(self, cls):
        ret = cls()
        for fieldname in (
            "point_cost", "time_cost", "name", "title", "description", "state",
            "collaborators", "assignee", "priority", "status_summary", "status_summary_time",
            "tags", "work_span", "tier", "uri", "loading_plugin",
        ):
            setattr(ret, fieldname, getattr(self, fieldname))
        ret.dependents = [d.as_class(cls) for d in self.dependents]

        return ret

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

    def save_metadata(self):
        raise NotImplementedError()

    @staticmethod
    def bulk_save_metadata(targets: typing.Iterable["BaseTarget"]):
        for target in targets:
            target.save_metadata()

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
