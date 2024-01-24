import datetime

import numpy as np

from ..history import Summary, Aggregation
from .. import utilities
from . import func, dist


class StatSummary(Summary):
    OUTLIER_THRESHOLD = -1

    def __init__(self, a: Aggregation, cutoff: datetime.datetime, samples: int=200):
        super().__init__(a, cutoff)
        self._samples = samples

        self.completion = (np.inf, np.inf)
        self.velocity_mean = 0
        self.velocity_stdev = 0
        self._projection_summary()

    def _projection_summary(self):
        todo = self.cutoff_todo + self.cutoff_underway

        if self.daily_velocity > 0:
            sl = func.get_pdf_bounds_slice(self._velocity_array)
            nonzero_daily_velocity = self._velocity_array[sl]

            v_mean, v_median = func.get_mean_median_dissolving_outliers(nonzero_daily_velocity, self.OUTLIER_THRESHOLD)
            self.velocity_mean = v_mean
            mu, sigma = func.get_lognorm_mu_sigma_from_lognorm_mean_variance(v_mean, v_median)
            self.velocity_stdev = v_mean * np.sqrt(np.exp(sigma ** 2) - 1)

            distro = dist.get_lognorm_given_mean_median(v_mean, v_median, self._samples)
            dom = np.linspace(0, v_mean, self._samples)
            velocity_pdf = distro.pdf(dom)
            dom *= 7

            completion_projection = func.construct_evaluation(dom, velocity_pdf, todo, 300)
            self.completion = (
                utilities.extent_index(completion_projection, 5),
                utilities.extent_index(completion_projection, 95),
            )
