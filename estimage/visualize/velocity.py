import typing
import datetime

import numpy as np

from . import utils
from .. import history, PluginResolver, statops


DAYS_IN_WEEK = 7


class TierStyle(typing.NamedTuple):
    label: str
    color: tuple


@PluginResolver.class_is_extendable("MPLVelocityPlot")
class MPLVelocityPlot:
    TIER_STYLES = (
        TierStyle(label="", color=(0.1, 0.1, 0.6, 1)),
    )
    DDAY_LABEL = "today"

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
        ax.plot(
            self.days, data, color=tier_style.color,
            label=f"{tier_style.label} Velocity Fit")

    def get_date_of_dday(self):
        return datetime.datetime.today()

    def get_figure(self, cutoff_date):
        plt = utils.get_standard_pyplot()

        fig, ax = plt.subplots()
        ax.grid(True)

        self._prepare_plots(cutoff_date)

        aggregate_focus = np.zeros_like(self.velocity_focus[0])
        for tier, tier_focus in enumerate(self.velocity_focus):
            aggregate_focus += tier_focus
            self._plot_velocity_tier(ax, aggregate_focus * DAYS_IN_WEEK, tier)
        all_tiers_rolling_velocity = np.sum(self.velocity_estimate, 0)
        ax.plot(
            self.days, all_tiers_rolling_velocity * DAYS_IN_WEEK,
            color="orange", label="Rolling velocity estimate")

        index_of_dday = history.days_between(self.start, self.get_date_of_dday())
        if 0 <= index_of_dday <= len(self.days):
            ax.axvline(index_of_dday, label=self.DDAY_LABEL, color="grey", linewidth=2)

        ax.legend(loc="upper center")
        utils.x_axis_weeks_and_months(ax, self.start, self.end)
        ax.set_ylabel("team velocity / points per week")

        return fig


@PluginResolver.class_is_extendable("VelocityFitPlot")
class MPLVelocityFitPlot:
    STYLES = dict(
        hist=dict(alpha=0.75),
        hist_likely=dict(color="b"),
        hist_spiked=dict(color="r"),
        fit_raw=dict(color="gray", linestyle="--"),
        fit_likely=dict(color="black"),
    )

    def __init__(self, nonzero_velocity_array):
        self.velocity_array = nonzero_velocity_array
        self.outlier_thresh = 3
        self.orderly_velocity, self.spiked_velocity = statops.separate_array_into_good_and_bad(
            nonzero_velocity_array, self.outlier_thresh)
        self.raw_fit = statops.get_lognorm_given_mean_median(
            nonzero_velocity_array.mean(), np.median(nonzero_velocity_array))
        mean, median = statops.get_mean_median_dissolving_outliers(
            self.velocity_array, self.outlier_thresh)
        self.orderly_fit = statops.get_lognorm_given_mean_median(mean, median)
        self._y_max = 0

    def _plot_histogram(self, ax):
        values, bins = np.histogram(self.velocity_array, bins="auto")
        self._y_max = values.max()
        style = self.STYLES["hist"] | self.STYLES["hist_likely"]
        ax.hist(self.orderly_velocity, bins, ** style, label="likely velocity")
        style = self.STYLES["hist"] | self.STYLES["hist_spiked"]
        ax.hist(self.spiked_velocity, bins, ** style, label="outliers")

    def _plot_fits(self, ax):
        dom = np.linspace(0, self.velocity_array.max() * 1.1, 200)
        hom = self.raw_fit.pdf(dom)
        style = self.STYLES["fit_raw"]
        ax.plot(dom, hom / hom.max() * self._y_max, ** style, label="fit of raw velocity")
        hom = self.orderly_fit.pdf(dom)
        style = self.STYLES["fit_likely"]
        ax.plot(dom, hom / hom.max() * self._y_max, ** style, label="fit of likely velocity")

    def get_figure(self):
        plt = utils.get_standard_pyplot()

        fig, ax = plt.subplots()
        ax.grid(True)
        ax.set_xlabel("team velocity / points per week")

        self._plot_histogram(ax)
        ax.set_ylabel("relative frequency")

        ax2 = ax.twinx()
        self._plot_fits(ax)
        ax2.set_ylabel("probability density")
        ax2.set_ylim(0, 1)
        ax2.set_yticklabels([])

        ax.set_xlim(0, None)
        ax.legend(loc="upper right")
        return fig
