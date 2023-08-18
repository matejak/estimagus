import datetime
import typing
import collections

import numpy as np

from .. import data
from .. import utilities
from ..entities import target

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


def convert_target_to_representation(
        source: target.BaseTarget,
        start: datetime.datetime, end: datetime.datetime) -> progress.Progress:
    repre = progress.Progress(start, end)
    repre.task_name = source.name
    repre.points_timeline.set_value_at(end, source.point_cost)
    repre.status_timeline.set_value_at(end, source.state)
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


def propagate_span_to_children(parent_span, child, start, end):
    if not parent_span:
        return
    child.work_span = produce_meaningful_span(parent_span, start, end)


def convert_target_to_representations_of_leaves(
        source: target.BaseTarget,
        start: datetime.datetime, end: datetime.datetime) -> typing.List[progress.Progress]:
    ret = []

    if source.dependents:
        for d in source.dependents:
            propagate_span_to_children(source.work_span, d, start, end)
            ret.extend(convert_target_to_representations_of_leaves(d, start, end))
    else:
        ret = [convert_target_to_representation(source, start, end)]
    return ret


def produce_tiered_aggregations(all_targets, all_events, start, end):
    targets_by_tiers = collections.defaultdict(list)
    for t in all_targets.values():
        targets_by_tiers[t.tier].append(t)

    aggregations = []
    for tier in range(max(targets_by_tiers.keys()) + 1):
        target_tree = utilities.reduce_subsets_from_sets(targets_by_tiers[tier])
        a = Aggregation.from_targets(target_tree, start, end)
        a.process_event_manager(all_events)
        aggregations.append(a)
    return aggregations


class Aggregation:
    repres: typing.List[progress.Progress]

    def __init__(self):
        self.repres = []

    @classmethod
    def from_target(
            cls, source: target.BaseTarget,
            start: datetime.datetime, end: datetime.datetime) -> "Aggregation":
        return cls.from_targets([source], start, end)

    @classmethod
    def from_targets(
            cls, sources: target.BaseTarget,
            start: datetime.datetime, end: datetime.datetime) -> "Aggregation":
        ret = cls()
        for s in sources:
            for r in convert_target_to_representations_of_leaves(s, start, end):
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

    def states_on(self, when):
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
        return self.repres[0].points_timeline.days

    def process_event_manager(self, manager: data.EventManager):
        events_by_taskname = dict()
        for repre in self.repres:
            name = repre.task_name
            events_by_taskname[name] = manager.get_chronological_task_events_by_type(name)
        return self.process_events_by_taskname_and_type(events_by_taskname)
