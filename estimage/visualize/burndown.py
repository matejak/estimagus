import datetime
import typing

import numpy as np

from ..entities.target import State
from . import utils
from .. import history


class StatusStyle(typing.NamedTuple):
    status: State
    color: tuple
    label: str


class MPLPointPlot:
    STYLES = (
        StatusStyle(status=State.todo, color=(0.1, 0.1, 0.5, 1), label="To Do"),
        StatusStyle(status=State.in_progress, color=(0.1, 0.1, 0.6, 0.8), label="In Progress"),
        StatusStyle(status=State.review, color=(0.1, 0.2, 0.7, 0.6), label="Needs Review"),
    )

    def __init__(self, a: history.Aggregation):
        self.aggregation = a
        self.status_arrays = np.zeros((len(self.STYLES), a.days))
        today_date = datetime.datetime.today()
        self.index_of_today = history.days_between(self.aggregation.start, today_date)
        self.width = 1.0

    def _prepare_plots(self):
        for index, style in enumerate(self.STYLES):
            for r in self.aggregation.repres:
                array = self.status_arrays[index]
                array[r.status_is(style.status)] += r.points_of_status(style.status)

    def _show_plan(self, ax):
        ax.plot(self.aggregation.get_plan_array(), color="orange",
                linewidth=self.width, label="burndown")

    def _show_today(self, ax):
        if self.aggregation.start <= datetime.datetime.today() <= self.aggregation.end:
            ax.axvline(self.index_of_today, label="today", color="grey", linewidth=self.width * 2)

    def _plot_prepared_arrays(self, ax):
        days = np.arange(self.aggregation.days)
        bottom = np.zeros_like(days, dtype=float)
        for index, style in enumerate(self.STYLES):
            array = self.status_arrays[index]
            self._plot_data_with_termination(ax, array, bottom, style)
            bottom += array

    def _plot_data_with_termination(self, ax, array, bottom, style):
        days = np.arange(self.aggregation.days)
        if 0 <= self.index_of_today < len(days):
            up_until_today = slice(0, self.index_of_today + 1)
            today = self.index_of_today
            array = utils.insert_element_into_array_after(array[up_until_today], today, 0)
            bottom = utils.insert_element_into_array_after(bottom[up_until_today], today, 0)
            days = utils.insert_element_into_array_after(days[up_until_today], today, today)
        ax.fill_between(days, array + bottom, bottom, label=style.label,
                        color=style.color, edgecolor="white", linewidth=self.width * 0.5)

    def get_figure(self):
        plt = utils.get_standard_pyplot()

        fig, ax = plt.subplots()
        ax.grid(True)

        self._prepare_plots()
        self._plot_prepared_arrays(ax)
        self._show_plan(ax)
        self._show_today(ax)
        ax.legend(loc="upper right")

        utils.x_axis_weeks_and_months(ax, self.aggregation.start, self.aggregation.end)
        ax.set_ylabel("points")

        return fig

    def get_small_figure(self):
        plt = utils.get_standard_pyplot()

        fig, ax = plt.subplots()

        self._prepare_plots()
        self._plot_prepared_arrays(ax)
        self._show_plan(ax)
        self._show_today(ax)

        ax.set_axis_off()
        fig.subplots_adjust(0, 0, 1, 1)

        return fig

    def plot_stuff(self):
        plt = utils.get_standard_pyplot()
        self.get_figure()

        plt.show()
