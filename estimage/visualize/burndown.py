import numpy as np
import datetime

from ..entities import target
from . import utils
from .. import history


class MPLPointPlot:
    def __init__(self, a: history.Aggregation):
        self.aggregation = a
        empty_array = np.zeros(a.days)
        self.styles = [
            (target.State.todo, empty_array.copy(), (0.1, 0.1, 0.5, 1)),
            (target.State.in_progress, empty_array.copy(), (0.1, 0.1, 0.6, 0.8)),
            (target.State.review, empty_array.copy(), (0.1, 0.2, 0.7, 0.6)),
        ]
        self.index_of_today = history.days_between(self.aggregation.start, datetime.datetime.today())
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
        plt = get_standard_pyplot()
        self.get_figure()

        plt.show()
