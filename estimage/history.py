import datetime
import typing
import collections
import dataclasses

import numpy as np

from .entities import target


ONE_DAY = datetime.timedelta(days=1)


def get_period(start: datetime.datetime, end: datetime.datetime):
    period = end - start
    return np.zeros(period.days)


def localize_event(
        start: datetime.datetime, evt: datetime.datetime):
    return (evt - start).days


@dataclasses.dataclass
class Event:
    time: datetime.datetime
    task_name: str
    quantity: str
    value_before: str
    value_after: str

    def __init__(self, task_name, quantity, time):
        self.time = time
        self.task_name = task_name
        self.quantity = quantity
        self.value_after = None
        self.value_before = None

    def __str__(self):
        return f"{self.time.date()} {self.quantity}: {self.value_before} -> {self.value_after}"

    @classmethod
    def last_points_measurement(cls, task_name, when, value):
        ret = cls(task_name, "points", when)
        ret.value_after = value
        ret.value_before = value
        return ret

    @classmethod
    def last_state_measurement(cls, task_name, when, value):
        ret = cls(task_name, "state", when)
        ret.value_after = target.State.unknown
        ret.value_before = value
        return ret


class EventManager:
    _events: typing.Dict[str, typing.List[Event]]

    def __init__(self):
        self._events = collections.defaultdict(list)

    def add_event(self, event: Event):
        events = self._events[event.task_name]
        events.append(event)
        self._events[event.task_name] = sorted(events, key=lambda e: e.time)

    def get_referenced_task_names(self):
        return set(self._events.keys())

    def get_chronological_events_concerning(self, task_name: str):
        sorted_events = []
        if task_name in self._events:
            sorted_events = self._events[task_name]
        return sorted_events

    def save(self):
        task_names = self.get_referenced_task_names()
        for name in task_names:
            self._save_task_events(name, self._events[name])

    def _save_task_events(self, task_name: str, event_list: typing.List[Event]):
        raise NotImplementedError()

    @classmethod
    def load(cls):
        result = cls()
        events_task_names = result._load_event_names()
        for name in events_task_names:
            result._events[name] = result._load_events(name)
        return result

    def _load_events(self, name):
        raise NotImplementedError()

    def _load_event_names(self):
        raise NotImplementedError()


class Timeline:
    _data: np.array
    start: datetime.datetime
    end: datetime.datetime

    def __init__(self, start: datetime.datetime, end: datetime.datetime):
        self.start = start
        self.end = end
        period = end - start
        self._data = np.zeros(period.days + 1)

    def recreate_with_value(self, value, dtype=float):
        self._data = np.empty_like(self._data, dtype=dtype)
        self._data[:] = value

    @property
    def days(self):
        return len(self._data)

    def process_events(self, events):
        if not events:
            return
        events = sorted(events, key=lambda x: x.time, reverse=True)
        self._data[:] = events[0].value_after
        indices = np.empty(len(events), dtype=int)
        for i, e in enumerate(events):
            index = localize_event(self.start, e.time)
            indices[i] = index
            if index >= len(self._data):
                msg = "Event outside of the timeline"
                raise ValueError(msg)
            self._data[0:index] = e.value_before

        for i, e in enumerate(events[::-1]):
            index = indices[-1 - i]
            self._data[index] = e.value_before

    def set_value_at(self, time: datetime.datetime, value):
        index = localize_event(self.start, time)
        self._data[index] = value

    def value_at(self, time: datetime.datetime):
        index = localize_event(self.start, time)
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
    time_timeline: Timeline
    task_name: str

    def __init__(self, start, end):
        self.points_timeline = Timeline(start, end)
        self.status_timeline = Timeline(start, end)
        self.status_timeline.recreate_with_value(target.State.unknown)
        self.time_timeline = Timeline(start, end)
        self.start = start
        self.end = end
        self.task_name = ""

    def update(self, when, status=None, points=None, time=None):
        if points is not None:
            self.points_timeline.set_value_at(when, points)
        if status is not None:
            self.status_timeline.set_value_at(when, status)
        if time is not None:
            self.time_timeline.set_value_at(when, status)

    def get_points_at(self, when):
        return self.points_timeline.value_at(when)

    def get_status_at(self, when):
        return self.status_timeline.value_at(when)

    def status_is(self, status: target.State):
        return self.status_timeline.get_value_mask(status)

    def points_of_status(self, status):
        mask = self.status_is(status)
        return self.points_timeline.get_masked_values(mask)

    def fill_history_from(self, when):
        init_event = Event("", "points", when)

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
                deadline_index = localize_event(self.start, latest_at)
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

    def get_velocity_array(self):
        if not self.is_done():
            return self.status_timeline.get_value_mask(target.State.done).astype(float)
        velocity_array = self.status_timeline.get_value_mask(target.State.in_progress).astype(float)
        if velocity_array.sum() == 0:
            index_of_completion = localize_event(self.start, self.get_day_of_completion())
            velocity_array[index_of_completion] = 1
        velocity_array *= self.points_completed() / velocity_array.sum()
        return velocity_array

    def process_events(self, events_by_type):
        TYPES_TO_TIMELINE = {
            "time": self.time_timeline,
            "points": self.points_timeline,
            "state": self.status_timeline
        }
        for event_type, timeline in TYPES_TO_TIMELINE.items():
            events = events_by_type.get(event_type, [])
            timeline.process_events(events)


def _convert_target_to_representation(
        source: target.BaseTarget,
        start: datetime.datetime, end: datetime.datetime) -> typing.List[Repre]:
    repre = Repre(start, end)
    repre.task_name = source.name
    repre.points_timeline.set_value_at(end, source.point_cost)
    repre.status_timeline.set_value_at(end, source.state)
    repre.fill_history_from(end)
    return repre


def convert_target_to_representations_of_leaves(
        source: target.BaseTarget,
        start: datetime.datetime, end: datetime.datetime) -> typing.List[Repre]:
    ret = []
    if source.dependents:
        for d in source.dependents:
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
        ret = cls()
        for r in convert_target_to_representations_of_leaves(source, start, end):
            ret.add_repre(r)
        return ret

    def process_events(self, events: typing.Iterable[Event]):
        events_by_taskname = collections.defaultdict(lambda: collections.defaultdict(list))
        for evt in events:
            events_by_taskname[evt.task_name][evt.quantity].append(evt)

        for r in self.repres:
            if (task_name := r.task_name) in events_by_taskname:
                r.process_events(events_by_taskname[task_name])

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


class MPLPointPlot:
    def __init__(self, a: Aggregation):
        self.aggregation = a
        empty_array = np.zeros(a.days)
        self.styles = [
            (target.State.todo, empty_array.copy(), (0.1, 0.1, 0.5, 1)),
            (target.State.in_progress, empty_array.copy(), (0.1, 0.1, 0.6, 0.8)),
            (target.State.review, empty_array.copy(), (0.1, 0.2, 0.7, 0.6)),
        ]

    def _prepare_plots(self):
        for status, dest, color in self.styles:
            for r in self.aggregation.repres:
                dest[r.status_is(status)] += r.points_of_status(status)

    def _plot_bars(self, ax):
        width = 1.0
        days = np.arange(self.aggregation.days)
        bottom = np.zeros_like(days, dtype=float)
        for status, array, color in self.styles:
            ax.bar(days, array, width, bottom=bottom, label=status, color=color)
            bottom += array

        ax.plot([days[0], days[-1]], [bottom[0], 0], color="blue")

    def plot_stuff(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.grid(True)

        self._prepare_plots()
        self._plot_bars(ax)
        ax.legend()
        ax.set_xlabel("time / days")
        ax.set_ylabel("points")

        plt.show()


class MPLVelocityPlot:
    def __init__(self, a: Aggregation):
        self.aggregation = a
        self.velocity_estimate = np.zeros(a.days)
        self.velocity_focus = np.zeros(a.days)
        self.days = np.arange(a.days)

    def _prepare_plots(self, cutoff_date):
        start_date = self.aggregation.repres[0].start
        for r in self.aggregation.repres:
            self.velocity_focus += r.get_velocity_array()

            for days in range(self.aggregation.days):
                date = start_date + ONE_DAY * days
                self.velocity_estimate[days] += r.points_completed(date) / (days + 1)

                if date == cutoff_date:
                    break

    def plot_stuff(self, cutoff_date):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.grid(True)

        self._prepare_plots(cutoff_date)

        ax.plot(self.days, self.velocity_focus, label="Velocity Focus")
        ax.plot(self.days, self.velocity_estimate, label="Velocity Estimate")

        ax.legend()
        ax.set_xlabel("time / days")
        ax.set_ylabel("velocity")

        plt.show()
