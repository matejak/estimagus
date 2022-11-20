import datetime
import enum
import typing

import numpy as np


def get_period(start: datetime.datetime, end: datetime.datetime):
    period = end - start
    return np.zeros(period.days)


def localize_event(
        start: datetime.datetime, evt: datetime.datetime):
    return (evt - start).days


class Event:
    time: datetime.datetime
    task_name: str

    def __init__(self, task_name, time):
        self.time = time
        self.task_name = task_name
        self.value = None

    def __str__(self):
        return f"{self.time.date()}: {self.value}"


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
        events = sorted(events, key=lambda x: x.time, reverse=True)
        indices = np.empty(len(events), dtype=int)
        for i, e in enumerate(events):
            index = localize_event(self.start, e.time)
            indices[i] = index
            if index >= len(self._data):
                msg = "Event outside of the timeline"
                raise ValueError(msg)
            self._data[0:index] = e.value

        for i, e in enumerate(events[::-1]):
            index = indices[-1 - i]
            self._data[index] = e.value

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


class State(enum.IntEnum):
    unknown = enum.auto()
    backlog = enum.auto()
    todo = enum.auto()
    in_progress = enum.auto()
    review = enum.auto()
    done = enum.auto()
    abandoned = enum.auto()


class Repre:
    points_timeline: Timeline
    status_timeline: Timeline
    time_timeline: Timeline

    def __init__(self, start, end):
        self.points_timeline = Timeline(start, end)
        self.status_timeline = Timeline(start, end)
        self.status_timeline.recreate_with_value(State.unknown)
        self.time_timeline = Timeline(start, end)

    def update(self, when, status=None, points=None, time=None):
        if points is not None:
            self.points_timeline.set_value_at(when, points)
        if status is not None:
            self.status_timeline.set_value_at(when, status)

    def get_points_at(self, when):
        return self.points_timeline.value_at(when)

    def get_status_at(self, when):
        return self.status_timeline.value_at(when)

    def status_is(self, status: State):
        return self.status_timeline.get_value_mask(status)

    def points_of_status(self, status):
        mask = self.status_is(status)
        return self.points_timeline.get_masked_values(mask)

    def fill_history_from(self, when):
        init_event = Event("", when)

        init_event.value = self.points_timeline.value_at(when)
        self.points_timeline.process_events([init_event])

        init_event.value = self.status_timeline.value_at(when)
        self.status_timeline.process_events([init_event])

    def is_done(self):
        done_mask = self.status_timeline.get_value_mask(State.done)
        task_done = done_mask.sum() > 0
        return task_done

    def done_task_points(self):
        if not self.is_done():
            return 0
        done_mask = self.status_timeline.get_value_mask(State.done)
        task_points = self.points_timeline.get_masked_values(done_mask)[-1]
        return task_points

    @property
    def velocity(self):
        in_progress_mask = self.status_timeline.get_value_mask(State.in_progress)
        time_taken = in_progress_mask.sum() or 1
        return self.done_task_points() / time_taken


class Aggregation:
    repres: typing.List[Repre]

    def __init__(self):
        self.repres = []

    def add_repre(self, repre):
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
    def days(self):
        return self.repres[0].points_timeline.days


class MPLPlot:
    def __init__(self, a: Aggregation):
        self.aggregation = a
        empty_array = np.zeros(a.days)
        self.styles = [
            (State.todo, empty_array.copy(), (0.1, 0.1, 0.5, 1)),
            (State.in_progress, empty_array.copy(), (0.1, 0.1, 0.6, 0.8)),
            (State.review, empty_array.copy(), (0.1, 0.2, 0.7, 0.6)),
        ]

    def _prepare_plots(self, up_to_date):
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

    def plot_stuff(self, up_to_date):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.grid(True)

        self._prepare_plots(up_to_date)
        self._plot_bars(ax)
        ax.legend()
        ax.set_xlabel("time / days")
        ax.set_ylabel("points")

        plt.show()


def demo_plot():
    start = datetime.datetime(2022, 10, 1)
    end = datetime.datetime(2022, 10, 21)

    ONE_DAY = datetime.timedelta(days=1)
    someday = datetime.datetime(2022, 10, 10)
    day_after = someday + ONE_DAY

    repre = Repre(start, end)

    repre.update(day_after, points=6, status=State.review)
    repre.update(someday, points=6, status=State.in_progress)
    repre.fill_history_from(someday)
    repre.update(someday - 3 * ONE_DAY, points=5, status=State.todo)
    repre.fill_history_from(someday - 3 * ONE_DAY)

    repre2 = Repre(start, end)
    repre2.update(day_after, points=8, status=State.todo)
    repre2.fill_history_from(day_after)

    aggregation = Aggregation()
    aggregation.add_repre(repre)
    aggregation.add_repre(repre2)

    plotter = MPLPlot(aggregation)
    plotter.plot_stuff(someday)
