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


def localize_date(
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

    def recreate_with_value(self, value, dtype=float):
        self._data = np.empty_like(self._data, dtype=dtype)
        self._data[:] = value

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
            index = localize_date(self.start, e.time)
            indices_from_newest[i] = index
            if not 0 <= index < len(self._data):
                msg = "Event outside of the timeline"
                raise ValueError(msg)
            self._data[0:index] = e.value_before

        indices_from_oldest = indices_from_newest[::-1]
        for i, e in zip(indices_from_oldest, events_from_oldest):
            self._data[i] = e.value_before

    def set_value_at(self, time: datetime.datetime, value):
        index = localize_date(self.start, time)
        self._data[index] = value

    def value_at(self, time: datetime.datetime):
        index = localize_date(self.start, time)
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
    relevancy_timeline: Timeline
    task_name: str

    def __init__(self, start, end):
        self.points_timeline = Timeline(start, end)
        self.status_timeline = Timeline(start, end)
        self.status_timeline.recreate_with_value(target.State.unknown)
        self.time_timeline = Timeline(start, end)
        self.relevancy_timeline = Timeline(start, end)
        self.relevancy_timeline.recreate_with_value(1)
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
        if not self.relevancy_timeline.value_at(when):
            return 0
        return self.points_timeline.value_at(when)

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
                deadline_index = localize_date(self.start, latest_at)
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
            index_of_completion = localize_date(self.start, self.get_day_of_completion())
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


def x_axis_weeks_and_months(ax, start, end):
    ticks = dict()
    set_week_ticks_to_mondays(ticks, start, end)
    set_ticks_to_months(ticks, start, end)

    ax.set_xticks(list(ticks.keys()))
    ax.set_xticklabels(list(ticks.values()), rotation=60)

    ax.set_xlabel("time / weeks")


def set_week_ticks_to_mondays(ticks, start, end):
    week_index = 0
    if start.weekday != 0:
        week_index = 1
    for day in range((end - start).days):
        if (start + day * ONE_DAY).weekday() == 0:
            ticks[day] = str(week_index)
            week_index += 1


def set_ticks_to_months(ticks, start, end):
    for day in range((end - start).days):
        if (the_day := (start + day * ONE_DAY)).day == 1:
            ticks[day] = datetime.date.strftime(the_day, "%b")


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
        index_of_today = localize_date(self.aggregation.start, datetime.datetime.today())
        for status, array, color in self.styles:
            if 0 <= index_of_today <= len(days):
                array[index_of_today:] = array[index_of_today]
            ax.fill_between(days, array + bottom, bottom, label=status,
                            color=color, edgecolor="white", linewidth=width * 0.5)
            bottom += array

        ax.plot([days[0], days[-1]], [bottom[0], 0], color="blue", linewidth=width)
        if 0 <= index_of_today <= len(days):
            ax.axvline(index_of_today, label="today", color="grey", linewidth=width * 2)

    def get_figure(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.grid(True)

        self._prepare_plots()
        self._plot_bars(ax)
        ax.legend(loc="upper right")

        r = self.aggregation.repres[0]
        x_axis_weeks_and_months(ax, r.start, r.end)
        ax.set_ylabel("points")

        return fig

    def plot_stuff(self):
        import matplotlib.pyplot as plt
        self.get_figure()

        plt.show()


class MPLVelocityPlot:
    def __init__(self, a: Aggregation):
        self.aggregation = a
        self.velocity_estimate = np.zeros(a.days)
        self.velocity_focus = np.zeros(a.days)
        self.days = np.arange(a.days)

    def _prepare_plots(self, cutoff_date):
        start_date = self.aggregation.start
        for r in self.aggregation.repres:
            self.velocity_focus += r.get_velocity_array()

            for days in range(self.aggregation.days):
                date = start_date + ONE_DAY * days
                self.velocity_estimate[days] += r.points_completed(date) / (days + 1)

                if date == cutoff_date:
                    break

    def plot_stuff(self, cutoff_date):
        import matplotlib.pyplot as plt
        self.get_figure(cutoff_date)

        plt.show()

    def get_figure(self, cutoff_date):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.grid(True)

        days_in_real_week = 7

        self._prepare_plots(cutoff_date)

        ax.plot(self.days, self.velocity_focus * days_in_real_week, label="Velocity retrofit")
        ax.plot(self.days, self.velocity_estimate * days_in_real_week, label="Rolling velocity estimate")

        index_of_today = localize_date(self.aggregation.start, datetime.datetime.today())
        if 0 <= index_of_today <= len(self.days):
            ax.axvline(index_of_today, label="today", color="grey", linewidth=2)

        ax.legend(loc="upper center")
        r = self.aggregation.repres[0]
        x_axis_weeks_and_months(ax, r.start, r.end)
        ax.set_ylabel("team velocity / points per week")

        return fig


def simplify_timeline_array(array_to_simplify):
    if len(array_to_simplify) < 3:
        return array_to_simplify
    simplified = [array_to_simplify[0]]
    for first, middle, last in zip(array_to_simplify[:-2], array_to_simplify[1:-1], array_to_simplify[2:]):
        if np.all(first[1:] == middle[1:]) * np.all(middle[1:] == last[1:]):
            continue
        simplified.append(middle)
    simplified.append(array_to_simplify[-1])
    return np.array(simplified, dtype=array_to_simplify.dtype)
