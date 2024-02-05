import datetime

import numpy as np
import scipy as sp

from ..history import Summary, Aggregation
from .. import utilities
from . import func


class StatSummary(Summary):
    OUTLIER_THRESHOLD = -1

    def __init__(self, a: Aggregation, cutoff: datetime.datetime, samples: int=200):
        super().__init__(a, cutoff)
        self._samples = samples

        self.weekly_completion = (np.inf, np.inf)
        self.weekly_velocity_mean = 0
        self.weekly_velocity_stdev = 0
        self._projection_summary()

    def _projection_summary(self):
        todo = self.cutoff_todo + self.cutoff_underway

        if self.daily_velocity > 0:
            nonzero_daily_velocity = func.get_nonzero_velocity(self._velocity_array)

            mu, sigma = func.autoestimate_lognorm(nonzero_daily_velocity)
            distro = sp.stats.lognorm(scale=np.exp(mu), s=sigma)

            daily_velocity_mean = distro.mean()
            daily_velocity_stdev = np.sqrt(distro.var())

            self.weekly_completion = (
                func.get_time_to_completion(daily_velocity_mean, daily_velocity_stdev, todo, 0.05) / 7,
                func.get_time_to_completion(daily_velocity_mean, daily_velocity_stdev, todo, 0.95) / 7,
            )

            self.weekly_velocity_mean = 7 * daily_velocity_mean
            self.weekly_velocity_stdev = np.sqrt(7) * daily_velocity_stdev
