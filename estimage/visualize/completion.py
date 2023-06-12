import typing
import datetime

import numpy as np

from . import utils
from .. import utilities


class MPLCompletionPlot:
    width = 2

    def __init__(self, todo_estimation, perweek_velocity_mean_std):
        dom, pdf = todo_estimation.divide_by_gauss_pdf(200, * perweek_velocity_mean_std)
        self.distribution = utilities.get_random_variable(dom, pdf)
        DAYS_IN_WEEK = 7
        lower_bound = self.distribution.ppf(0.02)
        upper_bound = self.distribution.ppf(0.98)
        self.dom = np.arange(
                int(np.floor(lower_bound * DAYS_IN_WEEK)),
                int(np.ceil(upper_bound * DAYS_IN_WEEK)) + 1)
        self.probs = self.distribution.cdf(self.dom / DAYS_IN_WEEK)
        self.probs -= self.probs[0]
        self.probs /= self.probs[-1]
        self.probs *= 100

    def _calculate_plan_wrt_day(self, ax, start):
        ax.plot(self.dom, self.probs, color="green",
                linewidth=self.width, label="prob of completion")
        utils.x_axis_weeks_and_months(ax, start, start + utils.ONE_DAY * self.dom[-1])

    def get_figure(self):
        plt = utils.get_standard_pyplot()

        fig, ax = plt.subplots()
        ax.grid(True)

        self._calculate_plan_wrt_day(ax, datetime.datetime.today())
        ax.legend(loc="upper left")

        ax.set_ylabel("percents")

        return fig

    def plot_stuff(self):
        plt = utils.get_standard_pyplot()
        self.get_figure()

        plt.show()
