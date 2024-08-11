import numpy as np

from ... import data
from ...entities import estimate
from ... import persistence


EXPORTS = dict(
    BaseCard="IntervalCard",
)


def lognorm_shape_to_c_of_v(shape):
    return np.sqrt(np.exp(shape ** 2) - 1)


DEFAULT_CV = lognorm_shape_to_c_of_v(0.26)


class IntervalCard(data.BaseCard):

    @classmethod
    def create_estim_input(cls, expected, coef_of_var=DEFAULT_CV, gamma=4):
        ret = data.EstimInput(expected)
        lognorm_shape = np.sqrt(np.log(coef_of_var ** 2 + 1))
        lognorm_scale = expected / np.exp(lognorm_shape ** 2 / 2.0)
        lognorm_skewness = (np.exp(lognorm_shape ** 2) + 2) * np.sqrt(np.exp(lognorm_shape ** 2) - 1)
        lognorm_variance = coef_of_var ** 2 * expected ** 2
        ret.GAMMA = gamma
        o, p, m = estimate.calculate_o_p_m_ext(expected, lognorm_variance, lognorm_skewness, ret.GAMMA)
        if not o <= m <= p:
            msg = (
                    "Constraints don't allow creation of such lognorm-like PERT distribution "
                    f"for PERT gamma parameter as low as {ret.GAMMA}")
            raise ValueError(msg)
        ret.optimistic = o
        ret.most_likely = m
        ret.pessimistic = p
        return ret

    def populate_taskmodel(self, result, statuses):
        super().populate_taskmodel(result, statuses)
        if self.point_cost:
            expected = self.point_cost

            inp = self.create_estim_input(self.point_cost)

            result.point_estimate = data.Estimate.from_input(inp)
        return result
