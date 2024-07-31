
from ... import data


class IntervalCard(data.BaseCard):
    def populate_taskmodel(self, result, statuses):
        super().populate_taskmodel(result, statuses)
        if self.point_cost:
            expected = self.point_cost

            inp = data.EstimInput(expected)
            inp.LAMBDA = 4
            inp.optimistic = expected * 0.468
            inp.most_likely = expected * 0.904
            inp.pessimistic = expected * 1.92

            result.point_estimate = data.Estimate.from_input(inp)
        return result
