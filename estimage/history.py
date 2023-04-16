import datetime
import typing
import collections

import numpy as np

from .entities import target
from . import data


ONE_DAY = datetime.timedelta(days=1)


def get_period(start: datetime.datetime, end: datetime.datetime):
    period = end - start
    return np.zeros(period.days)


def days_between(
        start: datetime.datetime, evt: datetime.datetime):
    return (evt - start).days


class Timeline:
    _data: np.array
    start: datetime.datetime
    end: datetime.datetime

    def __init__(self, start: datetime.datetime, end: datetime.datetime):
        self.start = start
        self.end = end
        period = end - start
        self._data = np.zeros(period.days + 1)

    def _localize_date(self, date: datetime.datetime):
        return (date - self.start).days

    def recreate_with_value(self, value, dtype=float):
        self._data = np.empty_like(self._data, dtype=dtype)
        self._data[:] = value

    def set_gradient_values(self,
                            start: datetime.datetime, start_value: float,
                            end: datetime.datetime, end_value: float):
        start_index = self._localize_date(start)
        end_index = self._localize_date(end) + 1
        values = np.linspace(start_value, end_value, end_index - start_index)
        self._data[start_index:end_index] = values
        self.set_value_at(start, start_value)
        self.set_value_at(end, end_value)

    def get_array(self):
        return self._data.copy()

    @property
    def days(self):
        return len(self._data)

    def process_events(self, events):
        if not events:
            return
        events_from_oldest = sorted(events, key=lambda x: x.time)
        events_from_newest = events_from_oldest[::-1]
        self._data[:] = events_from_newest[0].value_after
        indices_from_newest = np.empty(len(events_from_newest), dtype=int)
        for i, e in enumerate(events_from_newest):
            index = self._localize_date(e.time)
            indices_from_newest[i] = index
            if not 0 <= index < len(self._data):
                msg = "Event outside of the timeline"
                raise ValueError(msg)
            self._data[0:index] = e.value_before

        indices_from_oldest = indices_from_newest[::-1]
        for i, e in zip(indices_from_oldest, events_from_oldest):
            self._data[i] = e.value_before

    def set_value_at(self, time: datetime.datetime, value):
        index = self._localize_date(time)
        self._data[index] = value

    def value_at(self, time: datetime.datetime):
        index = self._localize_date(time)
        return self._data[index]

    def get_value_mask(self, value):
        return self._data == value

    def get_masked_values(self, mask):
        return self._data[mask]


class Repre:
    start: datetime.datetime
    end: datetime.datetime
    points_timeline: Timeline
    status_timeline: Timeline
    plan_timeline: Timeline
    time_timeline: Timeline
    relevancy_timeline: Timeline
    task_name: str

    def __init__(self, start, end):
        self.start = start
        self.end = end

        self.points_timeline = Timeline(start, end)
        self.status_timeline = Timeline(start, end)
        self.status_timeline.recreate_with_value(target.State.unknown)
        self.time_timeline = Timeline(start, end)

        self.plan_timeline = Timeline(start, end)
        self.calculate_plan()

        self.relevancy_timeline = Timeline(start, end)
        self.relevancy_timeline.recreate_with_value(1)
        self.task_name = ""

    def calculate_plan(self, work_start=None, work_end=None):
        start = work_start or self.start
        end = work_end or self.end
        self.plan_timeline.set_gradient_values(start, 1, end, 0)

    def update(self, when, status=None, points=None, time=None):
        if points is not None:
            self.points_timeline.set_value_at(when, points)
        if status is not None:
            self.status_timeline.set_value_at(when, status)
        if time is not None:
            self.time_timeline.set_value_at(when, status)

    def get_points_at(self, when):
        if not self.relevancy_timeline.value_at(when):
            return 0
        return self.points_timeline.value_at(when)

    def always_was_irrelevant(self):
        relevant_mask = self.status_timeline.get_value_mask(target.State.todo)
        relevant_mask |= self.status_timeline.get_value_mask(target.State.in_progress)
        relevant_mask |= self.status_timeline.get_value_mask(target.State.review)
        if sum(relevant_mask):
            return False
        return True

    def get_last_point_value(self):
        nonzero_mask = np.logical_not(self.points_timeline.get_value_mask(0))
        if sum(nonzero_mask) == 0:
            return 0
        ret = self.points_timeline.get_masked_values(nonzero_mask)[-1]
        return ret

    def get_status_at(self, when):
        if not self.relevancy_timeline.value_at(when):
            return target.State.unknown
        return self.status_timeline.value_at(when)

    def status_is(self, status: target.State):
        return self.status_timeline.get_value_mask(status)

    def points_of_status(self, status):
        mask = self.status_is(status)
        return self.points_timeline.get_masked_values(mask)

    def fill_history_from(self, when):
        init_event = data.Event("", "points", when)

        init_event.value_before = self.points_timeline.value_at(when)
        self.points_timeline.process_events([init_event])

        init_event.value_before = self.status_timeline.value_at(when)
        self.status_timeline.process_events([init_event])

    def is_done(self, latest_at=None):
        relevant_slice = slice(0, None)
        if latest_at is not None:
            if latest_at < self.start:
                return False
            elif latest_at < self.end:
                deadline_index = days_between(self.start, latest_at)
                relevant_slice = slice(0, deadline_index + 1)
        done_mask = self.status_timeline.get_value_mask(target.State.done)[relevant_slice]
        task_done = done_mask.sum() > 0
        return task_done

    def points_completed(self, before=None):
        if not self.is_done(before):
            return 0
        done_mask = self.status_timeline.get_value_mask(target.State.done)
        task_points = self.points_timeline.get_masked_values(done_mask)[-1]
        return task_points

    @property
    def average_daily_velocity(self):
        in_progress_mask = self.status_timeline.get_value_mask(target.State.in_progress)
        time_taken = in_progress_mask.sum() or 1
        return self.points_completed() / time_taken

    def get_day_of_completion(self):
        done_mask = self.status_timeline.get_value_mask(target.State.done)
        if done_mask.sum() == 0:
            return None
        indices = np.arange(len(done_mask))
        days_from_start_to_completion = indices[done_mask][0]
        return self.start + ONE_DAY * days_from_start_to_completion

    def get_plan_array(self):
        points_multiplier = self.get_last_point_value()
        if self.always_was_irrelevant():
            points_multiplier *= 0
        return self.plan_timeline.get_array() * points_multiplier

    def get_velocity_array(self):
        if not self.is_done():
            return self.status_timeline.get_value_mask(target.State.done).astype(float)
        velocity_array = self.status_timeline.get_value_mask(target.State.in_progress).astype(float)
        if velocity_array.sum() == 0:
            index_of_completion = days_between(self.start, self.get_day_of_completion())
            if index_of_completion == 0:
                return velocity_array
            velocity_array[index_of_completion] = 1
        velocity_array *= self.points_completed() / velocity_array.sum()
        return velocity_array

    def _extract_time_relevant_events(self, events: typing.Iterable[data.Event]):
        return [
            evt for evt in events if self.start <= evt.time <= self.end
        ]

    def process_events(self, events: typing.List[data.Event]):
        events_by_type = collections.defaultdict(list)
        for evt in events:
            events_by_type[evt.quantity].append(evt)
        self.process_events_by_type(events_by_type)

    def process_events_by_type(self, events_by_type: typing.Mapping[str, typing.List[data.Event]]):
        TYPES_TO_TIMELINE = {
            "time": self.time_timeline,
            "points": self.points_timeline,
            "state": self.status_timeline,
            "project": self.relevancy_timeline,
        }
        for event_type, timeline in TYPES_TO_TIMELINE.items():
            events = events_by_type.get(event_type, [])
            events = self._extract_time_relevant_events(events)
            timeline.process_events(events)


def apply_span_to_timeline(timeline, span, start, end):
    work_start = max(start, span[0])

    work_end = span[1]
    overflow_ratio = 0
    if span[1] > end:
        work_end = end
        overflow_ratio = (span[1] - end) / (span[1] - span[0])

    timeline.set_gradient_values(start, 1, work_start, 1)
    timeline.set_gradient_values(work_end, overflow_ratio, end, overflow_ratio)
    timeline.set_gradient_values(work_start, 1, work_end, overflow_ratio)


def _convert_target_to_representation(
        source: target.BaseTarget,
        start: datetime.datetime, end: datetime.datetime) -> typing.List[Repre]:
    repre = Repre(start, end)
    repre.task_name = source.name
    repre.points_timeline.set_value_at(end, source.point_cost)
    repre.status_timeline.set_value_at(end, source.state)
    if work_span := source.work_span:
        work_span = produce_meaningful_span(work_span, start, end)
        if work_span[1] < work_span[0]:
            msg = f"Inconsistent work span in {source.name}"
            raise ValueError(msg)
        apply_span_to_timeline(repre.plan_timeline, work_span, start, end)
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
        start: datetime.datetime, end: datetime.datetime) -> typing.List[Repre]:
    ret = []

    if source.dependents:
        for d in source.dependents:
            propagate_span_to_children(source.work_span, d, start, end)
            ret.extend(convert_target_to_representations_of_leaves(d, start, end))
    else:
        ret = [_convert_target_to_representation(source, start, end)]
    return ret


class Aggregation:
    repres: typing.List[Repre]

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
