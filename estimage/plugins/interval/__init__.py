
from ... import data


class IntervalCard(data.BaseCard):

    @classmethod
    def create_estim_input(cls, expected, coef_of_var=0.2643, gamma=4):
        ret = data.EstimInput(expected)
        ret.LAMBDA = 4
        ret.optimistic = expected * 0.468
        ret.most_likely = expected * 0.904
        ret.pessimistic = expected * 1.92
        return ret

    def populate_taskmodel(self, result, statuses):
        super().populate_taskmodel(result, statuses)
        if self.point_cost:
            expected = self.point_cost

            inp = self.create_estim_input(self.point_cost)

            result.point_estimate = data.Estimate.from_input(inp)
        return result
