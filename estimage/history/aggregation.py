import datetime
import typing
import collections
import dataclasses

import numpy as np

from .. import data
from .. import utilities
from ..entities import card, status

from . import progress


def _get_start_remainder(span, start, plan_length):
    planned_start, planned_end = span
    if planned_start >= start:
        return 1
    if planned_end < start:
        start_remainder = 0
    else:
        plan_before_period = start - planned_start
        start_remainder = 1 - plan_before_period / plan_length
    return start_remainder


def _get_end_remainder(span, end, plan_length):
    planned_start, planned_end = span
    if planned_end < end:
        return 0
    if planned_start > end:
        end_remainder = 1
    else:
        plan_after_period = planned_end - end
        end_remainder = plan_after_period / plan_length
    return end_remainder


def get_start_and_end_remainders(span, start, end):
    span_width = span[1] - span[0]
    start_remainder = _get_start_remainder(span, start, span_width)
    end_remainder = _get_end_remainder(span, end, span_width)

    return start_remainder, end_remainder


def apply_span_to_timeline(timeline, span, start, end):
    start_remainder, end_remainder = get_start_and_end_remainders(span, start, end)

    if start_remainder == 0:
        timeline.set_gradient_values(start, 0, end, 0)

    if end_remainder == 1:
        timeline.set_gradient_values(start, 1, end, 1)

    if end > span[0] > start:
        timeline.set_gradient_values(start, start_remainder, span[0], start_remainder)

    period_work_start = max(start, span[0])
    period_work_end = min(end, span[1])

    timeline.set_gradient_values(period_work_start, start_remainder, period_work_end, end_remainder)

    if end > span[1] > start:
        timeline.set_gradient_values(span[1], end_remainder, end, end_remainder)


def convert_card_to_representation(
        source: card.BaseCard,
        start: datetime.datetime, end: datetime.datetime,
        statuses: status.Statuses) -> progress.Progress:
    repre = progress.Progress(start, end, statuses)
    repre.task_name = source.name
    repre.points_timeline.set_value_at(end, source.point_cost)
    repre.set_status_at(end, source.status)
    if work_span := source.work_span:
        work_span = produce_meaningful_span(work_span, start, end)
        if work_span[1] < work_span[0]:
            msg = f"Inconsistent work span in {source.name}"
            raise ValueError(msg)
        apply_span_to_timeline(repre.remainder_timeline, work_span, start, end)
    repre.fill_history_from(end)
    return repre


def produce_meaningful_span(candidate_span, start, end):
    good_span = [start, end]
    if candidate_span[0] is not None:
        good_span[0] = candidate_span[0]
    if candidate_span[1] is not None:
        good_span[1] = candidate_span[1]
    good_span[1] = max(good_span[0], good_span[1])
    return tuple(good_span)


def recursively_propagate_span_to_children(current_card, start, end):
    if current_card.children:
        for d in current_card.children:
            propagate_span_to_children(current_card.work_span, d, start, end)
            recursively_propagate_span_to_children(d, start, end)


def propagate_span_to_children(parent_span, child, start, end):
    if not parent_span:
        return
    child.work_span = produce_meaningful_span(parent_span, start, end)


def propagate_span_from_parent(current_card, start, end):
    if current_card.parent:
        propagate_span_from_parent(current_card.parent, start, end)
        propagate_span_to_children(current_card.parent.work_span, current_card, start, end)


def convert_card_to_representations_of_leaves(
        source: card.BaseCard,
        start: datetime.datetime, end: datetime.datetime,
        statuses: status.Statuses) -> typing.List[progress.Progress]:
    ret = []

    propagate_span_from_parent(source, start, end)
    if source.children:
        for d in source.children:
            ret.extend(convert_card_to_representations_of_leaves(d, start, end, statuses))
            recursively_propagate_span_to_children(source, start, end)
    else:
        ret = [convert_card_to_representation(source, start, end, statuses)]
    return ret


def produce_tiered_aggregations(all_cards, all_events, start, end):
    cards_by_tiers = collections.defaultdict(list)
    for t in all_cards.values():
        cards_by_tiers[t.tier].append(t)

    aggregations = []
    for tier in range(max(cards_by_tiers.keys()) + 1):
        card_tree = utilities.reduce_subsets_from_sets(cards_by_tiers[tier])
        a = Aggregation.from_cards(card_tree, start, end)
        a.process_event_manager(all_events)
        aggregations.append(a)
    return aggregations


class Aggregation:
    repres: typing.List[progress.Progress]

    def __init__(self, statuses=None):
        self.repres = []
        self.statuses = statuses
        if not self.statuses:
            self.statuses = status.Statuses()

    @classmethod
    def from_card(
            cls, source: card.BaseCard,
            start: datetime.datetime, end: datetime.datetime,
            statuses: status.Statuses=None) -> "Aggregation":
        return cls.from_cards([source], start, end, statuses)

    @classmethod
    def from_cards(
            cls, sources: card.BaseCard,
            start: datetime.datetime, end: datetime.datetime,
            statuses: status.Statuses=None) -> "Aggregation":
        ret = cls(statuses)
        for s in sources:
            for r in convert_card_to_representations_of_leaves(s, start, end, ret.statuses):
                ret.add_repre(r)
        return ret

    def process_events(self, events: typing.Iterable[data.Event]):
        events_by_taskname = collections.defaultdict(lambda: collections.defaultdict(list))
        for evt in events:
            events_by_taskname[evt.task_name][evt.quantity].append(evt)
        self.process_events_by_taskname_and_type(events_by_taskname)

    def get_velocity_array(self):
        if not self.repres:
            return np.array([])
        ret = np.zeros_like(self.repres[0].get_velocity_array())
        for r in self.repres:
            ret += r.get_velocity_array()
        return ret

    def get_plan_array(self):
        if not self.repres:
            return np.array([])
        ret = np.zeros_like(self.repres[0].get_plan_array())
        for r in self.repres:
            ret += r.get_plan_array()
        return ret

    @property
    def point_velocity(self) -> data.Estimate:
        if not self.repres:
            return data.Estimate(0, 0)
        array = self.get_velocity_array()
        return data.Estimate(array.mean(), array.std())

    def process_events_by_taskname_and_type(
                self, events_by_taskname: typing.Mapping[str, data.Event]):
        for r in self.repres:
            if (task_name := r.task_name) in events_by_taskname:
                r.process_events_by_type(events_by_taskname[task_name])

    def add_repre(self, repre):
        if (self.end and self.end != repre.end) or (self.start and self.start != repre.start):
            msg = "Incompatible timespan of the representation"
            raise ValueError(msg)
        self.repres.append(repre)

    def statuses_on(self, when):
        states = set()
        for r in self.repres:
            states.add(r.get_status_at(when))
        return states

    def points_on(self, when):
        points = 0.0
        for r in self.repres:
            points += r.get_points_at(when)
        return points

    @property
    def start(self):
        if not self.repres:
            return None
        return self.repres[0].start

    @property
    def end(self):
        if not self.repres:
            return None
        return self.repres[0].end

    @property
    def days(self):
        if not self.repres:
            return 0
        return (self.end - self.start).days + 1

    def process_event_manager(self, manager: data.EventManager):
        events_by_taskname = dict()
        for repre in self.repres:
            name = repre.task_name
            events_by_taskname[name] = manager.get_chronological_task_events_by_type(name)
        return self.process_events_by_taskname_and_type(events_by_taskname)


ZERO_ESTIMATE_FIELD = dataclasses.field(default_factory=lambda: data.Estimate.from_triple(0, 0, 0))

@dataclasses.dataclass
class Summary:
    initial_todo: float = 0
    initial_done: float = 0
    cutoff_todo: float = 0
    cutoff_underway: float = 0
    cutoff_done: float = 0
    total_days_in_period: int = 0
    total_days_with_velocity: int = 0
    daily_velocity: float = 0
    nonzero_velocity: float = 0
    total_points_done: float = 0
    achieved_since_start: data.Estimate = ZERO_ESTIMATE_FIELD

    def __init__(self, a: Aggregation, cutoff: datetime.datetime):
        self.total_days_in_period = a.days
        self._start = a.start
        self._cutoff = cutoff
        for r in a.repres:
            self._process_repre(r)

        self._velocity_array = a.get_velocity_array()
        self.daily_velocity = self._velocity_array.mean()
        nonzero_velocity = self._velocity_array[self._velocity_array > 0]
        self.nonzero_velocity = nonzero_velocity.mean()
        self.total_days_with_velocity = len(nonzero_velocity)
        self.total_points_done = self.cutoff_done - self.initial_done

    def _process_repre(self, r):
        repre_points = r.get_points_at(self._start)
        if r.get_status_at(self._start).relevant_and_not_done_yet:
            self.initial_todo += repre_points
        status_at_cutoff = r.get_status_at(self._cutoff)
        if status_at_cutoff.relevant and status_at_cutoff.underway:
            self.cutoff_underway += repre_points
        elif status_at_cutoff.relevant and not status_at_cutoff.started:
            self.cutoff_todo += repre_points
        elif status_at_cutoff.relevant and status_at_cutoff.done:
            self.cutoff_done += repre_points
