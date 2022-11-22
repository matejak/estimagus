import dataclasses
import math

import numpy as np
import scipy as sp
import scipy.stats

from .. import utilities


# Don't set to 0, as the variance calculation tends to lose information
# when only the corresponding algorithm calculates the variance from the triple
SIGMA_LAMBDA = 0.1


def calculate_o_p(m, E, V, lam):
    """Given data, calculate optimistic and pessimistic numbers
    Args:
        m: Most likely
        E: Expected
        V: Variance
        lam: Lambda - between 0 and 1
    """
    double_a = 2 * lam - 9
    B = 6 * E * lam - 27 * E - 4 * lam * m + 18 * m
    B /= double_a
    D = 3 * math.sqrt(
        (
            2 * lam - 9)
        * (
            9 * E ** 2 * lam
            - 9 * E ** 2
            - 18 * E * lam * m
            + 18 * E * m
            + 9 * lam * m**2
            - 9 * m**2
            - 7 * V))
    D /= double_a
    return (B + D, B - D)


@dataclasses.dataclass
class EstimInput:
    optimistic: float
    most_likely: float
    pessimistic: float

    def __init__(self, value=0):
        self.optimistic = value
        self.most_likely = value
        self.pessimistic = value

    def distance_from(self, rhs: "EstimInput"):
        square_sum = (
            (self.optimistic - rhs.optimistic)**2
            + (self.most_likely - rhs.most_likely)**2
            + (self.pessimistic - rhs.pessimistic)**2
        )
        return math.sqrt(square_sum)

    def copy(self):
        ret = EstimInput(self.most_likely)
        ret.optimistic = self.optimistic
        ret.pessimistic = self.pessimistic
        return ret

    @classmethod
    def from_pert_and_data(cls, dom, values, expected, sigma):
        if sigma == 0:
            return cls(expected)
        ballpark_input = cls.from_pert_only(dom, values)
        m = ballpark_input.most_likely
        o, p = calculate_o_p(m, expected, sigma ** 2, SIGMA_LAMBDA)

        ret = cls(m)
        ret.optimistic = min(o, m)
        ret.pessimistic = max(p, m)
        return ret

    @classmethod
    def from_pert_only(cls, dom, values):
        for index, value in enumerate(values):
            if value > 0:
                optimistic = dom[index]
                break

        for index, value in enumerate(values[::-1]):
            if value > 0:
                pessimistic = dom[-1 - index]
                break

        most_likely_index = np.argmax(values)
        most_likely = dom[most_likely_index]
        ret = cls(most_likely)
        ret.optimistic = optimistic
        ret.pessimistic = pessimistic
        return ret


@dataclasses.dataclass
class Estimate:
    """
    An estimate of difficulty, represented by expected value and standard deviation.
    Typically, the 3-point source of the estimate is known and stored as source.

    Estimates can get composed, when the resulting estimate represents the estimation of
    all its constituents.
    """
    expected: float
    sigma: float

    source: EstimInput

    def __init__(self, expected, sigma):
        self.expected = expected
        self.sigma = sigma

        self.source = None
        if self.sigma == 0:
            self.source = EstimInput(self.expected)

    @classmethod
    def from_input(cls, inp: EstimInput):
        ret = cls.from_triple(inp.most_likely, inp.optimistic, inp.pessimistic)
        ret.source = inp.copy()
        return ret

    @classmethod
    def from_triple(cls, most_likely, optimistic, pessimistic):
        expected = (optimistic + pessimistic + 4 * most_likely) / 6
        sigma1 = math.sqrt((most_likely - optimistic) * (pessimistic - most_likely) / 7.0)
        var1 = sigma1**2
        sigma2 = (pessimistic - optimistic) / 6.0
        var2 = sigma2**2
        ret = cls(expected, math.sqrt(var1 * (1 - SIGMA_LAMBDA) + var2 * SIGMA_LAMBDA))
        ret.source = EstimInput(most_likely)
        ret.source.optimistic = optimistic
        ret.source.pessimistic = pessimistic
        return ret

    @property
    def variance(self):
        return self.sigma ** 2

    def __add__(self, rhs):
        result = self.compose_with(rhs)
        return result

    def get_pert_of_given_density(self, samples_per_unit=30):
        lower_bound = self.source.optimistic - 1
        upper_bound = self.source.pessimistic + 1
        dom = np.linspace(lower_bound, upper_bound,
                          round(samples_per_unit * (upper_bound - lower_bound)))
        return self.get_pert(dom=dom)

    def get_pert(self, num_samples=100, dom=None):
        if num_samples < 1:
            msg = (
                f"Invalid sample size {num_samples} - need at least 1"
            )
            raise ValueError(msg)

        if dom is None:
            dom = np.linspace(
                self.source.optimistic - 1, self.source.pessimistic + 1, num_samples + 2)
            dom = dom[1:-1]
        values = self._get_pert(dom)
        if len(dom) > 1:
            utilities.norm_pdf(values, dom[1] - dom[0])
        else:
            values[0] = 1

        return np.array([dom, values])

    def compose_with(self, rhs: "Estimate", samples_per_unit=30):
        if self.source is None or rhs.source is None:
            return self.compose_using_simple_values(rhs)
        return self.compose_using_pert_values(rhs, samples_per_unit)

    def compose_using_pert_values(self, rhs: "Estimate", samples_per_unit=30):
        if self.sigma > 0 and rhs.sigma > 0:
            pert = self._compose_using_pert(rhs, samples_per_unit)
            value_estimate = self.compose_using_simple_values(rhs)
            inp = EstimInput.from_pert_and_data(
                pert[0], pert[1], value_estimate.expected, value_estimate.sigma)
            return self.from_input(inp)
        else:
            return self._compose_using_shift(rhs)

    def compose_using_simple_values(self, rhs: "Estimate"):
        ret = Estimate(self.expected, self.sigma)
        ret.expected += rhs.expected
        ret.sigma = math.sqrt(self.variance + rhs.variance)
        ret.source = None
        return ret

    def _compose_using_shift(self, rhs: "Estimate"):
        ret = Estimate.from_input(self.source)
        ret.expected += rhs.expected
        ret.sigma += rhs.sigma
        if self.source and rhs.source:
            ret.source.optimistic += rhs.source.optimistic
            ret.source.most_likely += rhs.source.most_likely
            ret.source.pessimistic += rhs.source.pessimistic
        return ret

    def _compose_using_pert(self, rhs: "Estimate", samples_per_unit=20):
        dom_len_self = round((self.source.pessimistic - self.source.optimistic) * samples_per_unit)
        dom_len_rhs = round((rhs.source.pessimistic - rhs.source.optimistic) * samples_per_unit)
        composed_pert = self.compose_perts_of_same_scale(
            self.get_pert(dom_len_self), rhs.get_pert(dom_len_rhs))
        return composed_pert

    def compose_perts_of_same_scale(self, pert1, pert2):
        convolution = np.convolve(pert1[1], pert2[1])
        domain = np.linspace(
            pert1[0][0] + pert2[0][0],
            pert1[0][-1] + pert2[0][-1],
            len(convolution)
        )
        return np.array([domain, convolution])

    def _get_pert(self, domain):
        width = self.source.pessimistic - self.source.optimistic
        if width == 0:
            right_spot = np.argmin(np.abs(domain - self.source.most_likely))
            ret = np.zeros_like(domain)
            ret[right_spot] = 1.0
            return ret
        beta_a = 1 + 4 * (self.source.most_likely - self.source.optimistic) / width
        beta_b = 1 + 4 * (self.source.pessimistic - self.source.most_likely) / width
        values = sp.stats.beta.pdf(domain, beta_a, beta_b, scale=width, loc=self.source.optimistic)
        return values

    def rank_distance(self, estimate):
        """
        Given an estimate, return a float that
        is proportional to the differences between expected values and
        inversely proportional to the sum of standard deviations.

        If you are roughly after a value being within 2-sigma band,
        go for rank < 2, and so on
        """
        diff_of_expected = abs(estimate.expected - self.expected)
        sum_of_sigmas = estimate.sigma + self.sigma
        if diff_of_expected > 0 and sum_of_sigmas == 0:
            return float("inf")
        if diff_of_expected == 0:
            return 0
        return diff_of_expected / sum_of_sigmas
