import datetime

import numpy as np
import scipy as sp

from . import utils
from .. import utilities, PluginResolver


@PluginResolver.class_is_extendable("MPLCompletionPlot")
class MPLCompletionPlot:
    DDAY_LABEL = "today"
    width = 2

    def __init__(self, period_bounds, dom, cdf, ppf_cb):
        self.dom = dom
        self.cdf = cdf * 100
        self.period_start = period_bounds[0]
        self.period_end = period_bounds[1]
        self.chart_days_before_dday = - min(int(self.dom[0]), (self.period_end - self.get_date_of_dday()).days)
        self.chart_days_after_completion = max(0, (self.period_end - self.get_date_of_dday() + utils.ONE_DAY * self.dom[-1]).days)
        self.ppf = ppf_cb
        self._pad_dom_and_cdf()

    def _pad_dom_and_cdf(self):
        self.dom = np.concatenate((
            np.arange(- self.chart_days_before_dday, self.dom[0]),
            self.dom,
            np.arange(self.dom[-1], self.dom[-1] + self.chart_days_after_completion)))
        self.cdf = np.concatenate((
            np.zeros(self.chart_days_before_dday),
            self.cdf,
            np.ones(self.chart_days_after_completion) * 100))

    def _dom_to_days(self, dom_numbers):
        return dom_numbers - self.dom[0]

    def get_date_of_dday(self):
        return datetime.datetime(2024, 1, 28)
        return datetime.datetime.today()

    def _plot_plan_wrt_day(self, ax):
        start = self.get_date_of_dday()
        ax.plot(self._dom_to_days(self.dom), self.cdf, color="green",
                linewidth=self.width, label="prob of completion")

        chart_start = self.get_date_of_dday() + utils.ONE_DAY * self.dom[0]
        chart_end = self.get_date_of_dday() + utils.ONE_DAY * self.dom[-1]

        week_index = utils.get_week_index(self.period_start, chart_start)
        utils.x_axis_weeks_and_months(ax, chart_start, chart_end, week_index)

    def _plot_percentile(self, ax, value_in_percents):
        where = self.ppf(value_in_percents / 100.0)
        ax.axvline(self._dom_to_days(where), color="orange",
                   linewidth=self.width, label=f"confidence {round(value_in_percents)} %")

    def _plot_dday(self, ax):
        ax.axvline(self._dom_to_days(0), label=self.DDAY_LABEL, color="grey", linewidth=2)

    def _plot_period_end(self, ax):
        period_end_index = (self.period_end - self.get_date_of_dday()).days
        color = "blue"
        if period_end_index < 0:
            color = "red"
        ax.axvline(self._dom_to_days(period_end_index), label="period end", color=color, linewidth=2)

    def get_figure(self):
        plt = utils.get_standard_pyplot()

        fig, ax = plt.subplots()
        ax.grid(True)

        self._plot_plan_wrt_day(ax)
        if self.cdf[0] == 0:
            self._plot_percentile(ax, 95.0)
        self._plot_dday(ax)
        self._plot_period_end(ax)

        ax.legend(loc="upper left")

        ax.set_ylabel("percents")

        return fig

    def plot_stuff(self):
        plt = utils.get_standard_pyplot()
        self.get_figure()

        plt.show()
