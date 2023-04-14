import datetime
import typing
import collections

import numpy as np

from .entities import target
from . import data


ONE_DAY = datetime.timedelta(days=1)


def get_standard_pyplot():
    import matplotlib.pyplot as plt
    plt.rcParams['svg.fonttype'] = 'none'
    plt.rcParams['font.sans-serif'] = (
        "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Noto Sans", "Liberation Sans",
        "Arial,sans-serif" ,"Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji",
    )
    plt.rcParams['font.size'] = 12
    return plt


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


def insert_element_into_array_after(array: np.ndarray, index: int, value: typing.Any):
    separindex = index + 1
    components = (array[:separindex], np.array([value]), array[separindex:])
    return np.concatenate(components, 0)


class MPLPointPlot:
    def __init__(self, a: Aggregation):
        self.aggregation = a
        empty_array = np.zeros(a.days)
        self.styles = [
            (target.State.todo, empty_array.copy(), (0.1, 0.1, 0.5, 1)),
            (target.State.in_progress, empty_array.copy(), (0.1, 0.1, 0.6, 0.8)),
            (target.State.review, empty_array.copy(), (0.1, 0.2, 0.7, 0.6)),
        ]
        self.index_of_today = localize_date(self.aggregation.start, datetime.datetime.today())
        self.width = 1.0

    def _prepare_plots(self):
        for status, dest, color in self.styles:
            for r in self.aggregation.repres:
                dest[r.status_is(status)] += r.points_of_status(status)

    def _show_plan(self, ax):
        ax.plot(self.aggregation.get_plan_array(), color="orange",
                linewidth=self.width, label="burndown")

    def _show_today(self, ax):
        if self.aggregation.start <= datetime.datetime.today() <= self.aggregation.end:
            ax.axvline(self.index_of_today, label="today", color="grey", linewidth=self.width * 2)

    def _plot_prepared_arrays(self, ax):
        days = np.arange(self.aggregation.days)
        bottom = np.zeros_like(days, dtype=float)
        for status, array, color in self.styles:
            self._plot_data_with_termination(ax, status, array, bottom, color)
            bottom += array

    def _plot_data_with_termination(self, ax, status, array, bottom, color):
        days = np.arange(self.aggregation.days)
        if 0 <= self.index_of_today < len(days):
            array = insert_element_into_array_after(array[:self.index_of_today + 1], self.index_of_today, 0)
            bottom = insert_element_into_array_after(bottom[:self.index_of_today + 1], self.index_of_today, 0)
            days = insert_element_into_array_after(days[:self.index_of_today + 1], self.index_of_today, self.index_of_today)
        ax.fill_between(days, array + bottom, bottom, label=status,
                        color=color, edgecolor="white", linewidth=self.width * 0.5)

    def get_figure(self):
        plt = get_standard_pyplot()

        fig, ax = plt.subplots()
        ax.grid(True)

        self._prepare_plots()
        self._plot_prepared_arrays(ax)
        self._show_plan(ax)
        self._show_today(ax)
        ax.legend(loc="upper right")

        x_axis_weeks_and_months(ax, self.aggregation.start, self.aggregation.end)
        ax.set_ylabel("points")

        return fig

    def get_small_figure(self):
        plt = get_standard_pyplot()

        fig, ax = plt.subplots()

        self._prepare_plots()
        self._plot_prepared_arrays(ax)
        self._show_plan(ax)
        self._show_today(ax)

        ax.set_axis_off()
        fig.subplots_adjust(0, 0, 1, 1)

        return fig

    def plot_stuff(self):
        plt = get_standard_pyplot()
        self.get_figure()

        plt.show()


class MPLVelocityPlot:
    TIER_STYLES = [
        ("Committed", (0.1, 0.1, 0.7, 0.7)),
        ("Combined", (0.1, 0.1, 0.6, 1)),
    ]
    def __init__(self, a: typing.Iterable[Aggregation]):
        try:
            num_tiers = len(a)
        except TypeError:
            num_tiers = 1
            a = [a]
        self.aggregations_by_tiers = a
        self.velocity_estimate = np.zeros((num_tiers, a[0].days))
        self.velocity_focus = np.zeros((num_tiers, a[0].days))
        self.days = np.arange(a[0].days)
        self.start = a[0].start
        self.end = a[0].end

    def _prepare_plots(self, cutoff_date):
        for tier, aggregation in enumerate(self.aggregations_by_tiers):
            for r in aggregation.repres:
                self.velocity_focus[tier] += r.get_velocity_array()
                self._fill_rolling_velocity(tier, r, cutoff_date)

    def _fill_rolling_velocity(self, tier, repre, cutoff_date):
        completed_from_before = repre.points_completed(self.start)
        for days in self.days:
            date = self.start + ONE_DAY * days
            points_completed_to_date = repre.points_completed(date) - completed_from_before
            self.velocity_estimate[tier, days] += points_completed_to_date / (days + 1)

            if date >= cutoff_date:
                break

    def plot_stuff(self, cutoff_date):
        plt = get_standard_pyplot()
        self.get_figure(cutoff_date)

        plt.show()

    def _plot_velocity_tier(self, ax, data, tier):
        tier_style = self.TIER_STYLES[tier]
        if tier == 0:
            ax.fill_between(
                self.days, 0, data, color=tier_style[1],
                label=f"{tier_style[0]} Velocity retrofit")
        elif tier == 1:
            ax.plot(
                self.days, data, color=tier_style[1],
                label=f"{tier_style[0]} Velocity Retrofit")

    def get_figure(self, cutoff_date):
        plt = get_standard_pyplot()

        fig, ax = plt.subplots()
        ax.grid(True)

        days_in_real_week = 7

        self._prepare_plots(cutoff_date)

        aggregate_focus = np.zeros_like(self.velocity_focus[0])
        for tier, tier_focus in enumerate(self.velocity_focus):
            aggregate_focus += tier_focus
            self._plot_velocity_tier(ax, aggregate_focus * days_in_real_week, tier)
        all_tiers_rolling_velocity = np.sum(self.velocity_estimate, 0)
        ax.plot(
            self.days, all_tiers_rolling_velocity * days_in_real_week,
            color="orange", label="Rolling velocity estimate")

        index_of_today = localize_date(self.start, datetime.datetime.today())
        if 0 <= index_of_today <= len(self.days):
            ax.axvline(index_of_today, label="today", color="grey", linewidth=2)

        ax.legend(loc="upper center")
        x_axis_weeks_and_months(ax, self.start, self.end)
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
