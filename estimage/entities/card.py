import typing
import dataclasses
import datetime

from .estimate import Estimate
from .task import TaskModel
from . import status
from .composition import Composition
from .. import utilities, PluginResolver


@PluginResolver.class_is_extendable("BaseCard")
@dataclasses.dataclass(init=False)
class BaseCard:
    point_cost: float
    name: str
    title: str
    description: str
    children: typing.List["BaseCard"]
    parent: "BaseCard"
    depends_on: typing.List["BaseCard"]
    prerequisite_of: typing.List["BaseCard"]
    status: status.Status
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
        self.status = status.IRRELEVANT_STATUS.name
        self.collaborators = []
        self.assignee = ""
        self.priority = 50.0
        self.tags = set()
        self.work_span = None
        self.tier = 0
        self.uri = ""
        self.loading_plugin = ""

    def _convert_into_composition(self, statuses):
        ret = Composition(self.name)
        for d in self.children:
            if d.children:
                ret.add_composition(d._convert_into_composition(statuses))
            else:
                ret.add_element(d._convert_into_single_result(statuses))
        return ret

    def _convert_into_single_result(self, statuses):
        ret = TaskModel(self.name)
        if self.point_cost:
            ret.point_estimate = Estimate(self.point_cost, 0)

        try:
            if not statuses.get(self.status).relevant_and_not_done_yet:
                ret.mask()
        except KeyError as exc:
            msg = f"Card {self.name} features unknown status {self.status}"
            raise ValueError(msg)

        return ret

    def add_element(self, what: "BaseCard"):
        if what in self:
            return
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
        saver.save_priority_and_status(self)
        saver.save_tier(self)
        saver.save_tags(self)
        saver.save_work_span(self)
        saver.save_uri_and_plugin(self)

    def load_data_by_loader(self, loader):
        loader.load_title_and_desc(self)
        loader.load_costs(self)
        loader.load_family_records(self)
        loader.load_assignee_and_collab(self)
        loader.load_priority_and_status(self)
        loader.load_tier(self)
        loader.load_tags(self)
        loader.load_work_span(self)
        loader.load_uri_and_plugin(self)

    def __contains__(self, lhs: "BaseCard"):
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
    def to_tree(cls, cards: typing.List["BaseCard"], statuses: status.Statuses=None):
        if not statuses:
            statuses = status.Statuses()
        cards = utilities.reduce_subsets_from_sets(cards)

        result = Composition("")
        for t in cards:
            if t.children:
                result.add_composition(t._convert_into_composition(statuses))
            else:
                result.add_element(t._convert_into_single_result(statuses))
        return result.simplified()

    def get_tree(self, statuses: status.Statuses=None):
        return self.to_tree([self], statuses)


@PluginResolver.class_is_extendable("CardSynchronizer")
class CardSynchronizer:
    ABSOLUTE_TOLERABLE_DIFFERENCE = 0.1
    def get_tracker_points_of(self, card: BaseCard) -> float:
        raise NotImplementedError

    def set_tracker_points_of(self, card: BaseCard, target_points: float, card_io=None):
        real_points = self.get_tracker_points_of(card)
        self._synchronize_or_raise(card, real_points, target_points)
        card.point_cost = target_points
        if card_io:
            card.save_metadata(card_io)

    def _synchronize_or_raise(self, card: BaseCard, real_points: float, target_points: float):
        if real_points == target_points:
            return
        if abs(real_points - card.point_cost) > self.ABSOLUTE_TOLERABLE_DIFFERENCE:
            msg = (
                    f"Value of card '{card.name}' differs from expected value: "
                    f"{real_points} is not {card.point_cost} respectively "
                    f"by more than {self.ABSOLUTE_TOLERABLE_DIFFERENCE:.2g}."
            )
            raise ValueError(msg)
        self.insert_points_into_tracker(card, target_points)

    def insert_points_into_tracker(self, card: BaseCard, target_points: float):
        raise NotImplementedError
