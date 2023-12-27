import datetime
import collections
import typing

import numpy as np

from ..entities.card import Status
from . import utils
from .. import history, PluginResolver


class StatusStyle(typing.NamedTuple):
    color: tuple
    label: str


@PluginResolver.class_is_extendable("MPLPointPlot")
class MPLPointPlot:
    DDAY_LABEL = "today"

    def __init__(self, a: history.Aggregation, * args, ** kwargs):
        self.aggregation = a
        self.start = a.start
        self.end = a.end
        self.width = 1.0
        super().__init__(* args, ** kwargs)
        self.styles = get_styles()
        self.status_arrays = np.zeros((len(self.styles), a.days))
        dday_date = self.get_date_of_dday()
        self.index_of_dday = history.days_between(self.start, dday_date)


    def get_styles(self):
        ret = collections.OrderedDict(
            todo=StatusStyle(color=(0.1, 0.1, 0.5, 1), label="To Do"),
            in_progress=StatusStyle(color=(0.1, 0.1, 0.6, 0.8), label="In Progress"),
            #review=StatusStyle(color=(0.1, 0.2, 0.7, 0.6), label="Needs Review"),
        )
        return ret

    def get_date_of_dday(self):
        return datetime.datetime.today()

    def _prepare_plots(self):
        for index, status_name in enumerate(self.styles):
            for r in self.aggregation.repres:
                array = self.status_arrays[index]
                array[r.status_is(status_name)] += r.points_of_status(status_name)

    def _show_plan(self, ax):
        ax.plot(self.aggregation.get_plan_array(), color="orange",
                linewidth=self.width, label="burndown")

    def _show_dday(self, ax):
        if self.start <= self.get_date_of_dday() <= self.end:
            ax.axvline(self.index_of_dday, label=self.DDAY_LABEL, color="grey", linewidth=self.width * 2)

    def _plot_prepared_arrays(self, ax):
        days = np.arange(self.aggregation.days)
        bottom = np.zeros_like(days, dtype=float)
        for index, style in enumerate(self.styles.values()):
            array = self.status_arrays[index]
            self._plot_data_with_termination(ax, array, bottom, style)
            bottom += array

    def _plot_data_with_termination(self, ax, array, bottom, style):
        days = np.arange(self.aggregation.days)
        if 0 <= self.index_of_dday < len(days):
            up_until_dday = slice(0, self.index_of_dday + 1)
            dday = self.index_of_dday
            array = utils.insert_element_into_array_after(array[up_until_dday], dday, 0)
            bottom = utils.insert_element_into_array_after(bottom[up_until_dday], dday, 0)
            days = utils.insert_element_into_array_after(days[up_until_dday], dday, dday)
        if array.sum() > 0:
            ax.fill_between(days, array + bottom, bottom, label=style.label,
                            color=style.color, edgecolor="white", linewidth=self.width * 0.5)

    def get_figure(self):
        plt = utils.get_standard_pyplot()

        fig, ax = plt.subplots()
        ax.grid(True)

        self._prepare_plots()
        self._plot_prepared_arrays(ax)
        self._show_plan(ax)
        self._show_dday(ax)
        ax.legend(loc="upper right")

        utils.x_axis_weeks_and_months(ax, self.start, self.end)
        ax.set_ylabel("points")

        return fig

    def get_small_figure(self):
        plt = utils.get_standard_pyplot()

        fig, ax = plt.subplots()

        self._prepare_plots()
        self._plot_prepared_arrays(ax)
        self._show_plan(ax)
        self._show_dday(ax)

        ax.set_axis_off()
        fig.subplots_adjust(0, 0, 1, 1)

        return fig

    def plot_stuff(self):
        plt = utils.get_standard_pyplot()
        self.get_figure()

        plt.show()
