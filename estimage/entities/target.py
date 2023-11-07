import re
import typing
import enum
import dataclasses
import datetime

from .estimate import Estimate
from .task import TaskModel
from .composition import Composition
from .. import utilities, PluginResolver


class State(enum.IntEnum):
    unknown = enum.auto()
    backlog = enum.auto()
    todo = enum.auto()
    in_progress = enum.auto()
    review = enum.auto()
    done = enum.auto()
    abandoned = enum.auto()


@PluginResolver.class_is_extendable("BaseTarget")
@dataclasses.dataclass(init=False)
class BaseTarget:
    point_cost: float
    name: str
    title: str
    description: str
    children: typing.List["BaseTarget"]
    parent: "BaseTarget"
    depends_on: typing.List["BaseTarget"]
    prerequisite_of: typing.List["BaseTarget"]
    state: State
    collaborators: typing.List[str]
    assignee: str
    priority: float
    tags: typing.Set[str]
    work_span: typing.Tuple[datetime.datetime, datetime.datetime]
    tier: int
    uri: str
    loading_plugin: str

    def __init__(self, name: str, * args, **kwargs):
        super().__init__(* args, ** kwargs)

        self.point_cost = 0
        self.name = name
        self.title = ""
        self.description = ""
        self.children = []
        self.parent = None
        self.depends_on = []
        self.prerequisite_of = []
        self.state = State.unknown
        self.collaborators = []
        self.assignee = ""
        self.priority = 50.0
        self.tags = set()
        self.work_span = None
        self.tier = 0
        self.uri = ""
        self.loading_plugin = ""

    def _convert_into_composition(self):
        ret = Composition(self.name)
        for d in self.children:
            if d.children:
                ret.add_composition(d._convert_into_composition())
            else:
                ret.add_element(d._convert_into_single_result())
        return ret

    def _convert_into_single_result(self):
        ret = TaskModel(self.name)
        if self.point_cost:
            ret.point_estimate = Estimate(self.point_cost, 0)
        if self.state in (State.abandoned, State.done):
            ret.mask()
        return ret

    def add_element(self, what: "BaseTarget"):
        self.children.append(what)
        what.parent = self

    def save_metadata(self, saver_cls):
        with saver_cls.get_saver() as saver:
            self.pass_data_to_saver(saver)

    def pass_data_to_saver(self, saver):
        saver.save_title_and_desc(self)
        saver.save_costs(self)
        saver.save_family_records(self)
        saver.save_assignee_and_collab(self)
        saver.save_priority_and_state(self)
        saver.save_tier(self)
        saver.save_tags(self)
        saver.save_work_span(self)
        saver.save_uri_and_plugin(self)

    def load_data_by_loader(self, loader):
        loader.load_title_and_desc(self)
        loader.load_costs(self)
        loader.load_family_records(self)
        loader.load_assignee_and_collab(self)
        loader.load_priority_and_state(self)
        loader.load_tier(self)
        loader.load_tags(self)
        loader.load_work_span(self)
        loader.load_uri_and_plugin(self)

    def __contains__(self, lhs: "BaseTarget"):
        lhs_name = lhs.name

        if self.name == lhs.name:
            return True

        for rhs in self.children:
            if rhs.name == lhs_name:
                return True
            elif lhs in rhs:
                return True
        return False

    @classmethod
    def load_metadata(cls, name: str, loader_cls):
        ret = cls(name)
        with loader_cls.get_loader() as loader:
            ret.load_data_by_loader(loader)
        return ret

    @classmethod
    def to_tree(cls, targets: typing.List["BaseTarget"]):
        if not targets:
            return Composition("")
        targets = utilities.reduce_subsets_from_sets(targets)
        result = Composition("")
        if len(targets) == 1 and (target := targets[0]).children:
            result = target._convert_into_composition()
            return result
        for t in targets:
            if t.children:
                result.add_composition(t._convert_into_composition())
            else:
                result.add_element(t._convert_into_single_result())
        return result

    def get_tree(self):
        return self.to_tree([self])
