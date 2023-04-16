import typing
import datetime

import numpy as np

from . import utils
from .. import history


class MPLVelocityPlot:
    TIER_STYLES = [
        ("Committed", (0.1, 0.1, 0.7, 0.7)),
        ("Combined", (0.1, 0.1, 0.6, 1)),
    ]
    def __init__(self, a: typing.Iterable[history.Aggregation]):
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
            date = self.start + utils.ONE_DAY * days
            points_completed_to_date = repre.points_completed(date) - completed_from_before
            self.velocity_estimate[tier, days] += points_completed_to_date / (days + 1)

            if date >= cutoff_date:
                break

    def plot_stuff(self, cutoff_date):
        plt = utils.get_standard_pyplot()
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
        plt = utils.get_standard_pyplot()

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

        index_of_today = history.days_between(self.start, datetime.datetime.today())
        if 0 <= index_of_today <= len(self.days):
            ax.axvline(index_of_today, label="today", color="grey", linewidth=2)

        ax.legend(loc="upper center")
        utils.x_axis_weeks_and_months(ax, self.start, self.end)
        ax.set_ylabel("team velocity / points per week")

        return fig
