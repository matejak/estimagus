import datetime

import numpy as np

from . import utils
from .. import utilities, PluginResolver


DAYS_IN_WEEK = 7


@PluginResolver.class_is_extendable("CompletionPlot")
class MPLCompletionPlot:
    DDAY_LABEL = "today"
    width = 2

    def __init__(self, period_start, dist):
        self.period_start = self.get_date_of_dday() - utils.ONE_DAY
        self.distribution = dist
        upper_bound = self.distribution.ppf(0.98)
        self.dom = np.arange(
                - (self.get_date_of_dday() - period_start).days,
                int(np.ceil(upper_bound * DAYS_IN_WEEK)) + 1)
        self.probs = self.distribution.cdf(self.dom / DAYS_IN_WEEK)
        self.probs *= 100

    def _dom_to_days(self, dom_numbers):
        return dom_numbers - self.dom[0]

    def get_date_of_dday(self):
        return datetime.datetime.today()

    def _plot_plan_wrt_day(self, ax):
        start = self.get_date_of_dday()
        ax.plot(self._dom_to_days(self.dom), self.probs, color="green",
                linewidth=self.width, label="prob of completion")
        utils.x_axis_weeks_and_months(ax, start + utils.ONE_DAY * self.dom[0], start + utils.ONE_DAY * self.dom[-1])

    def _plot_percentile(self, ax, value_in_percents):
        where = self.distribution.ppf(value_in_percents / 100.0) * DAYS_IN_WEEK
        ax.axvline(self._dom_to_days(where), color="orange",
                   linewidth=self.width, label=f"confidence {round(value_in_percents)} %")
        where = self.distribution.mean() * DAYS_IN_WEEK
        ax.axvline(self._dom_to_days(where), color="black",
                   linewidth=self.width, label="Expected")

    def _plot_dday(self, ax):
        ax.axvline(self._dom_to_days(0), label=self.DDAY_LABEL, color="grey", linewidth=2)

    def get_figure(self):
        plt = utils.get_standard_pyplot()

        fig, ax = plt.subplots()
        ax.grid(True)

        self._plot_plan_wrt_day(ax)
        self._plot_percentile(ax, 95.0)
        self._plot_dday(ax)

        ax.legend(loc="upper left")

        ax.set_ylabel("percents")

        return fig

    def plot_stuff(self):
        plt = utils.get_standard_pyplot()
        self.get_figure()

        plt.show()
