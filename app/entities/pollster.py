import typing

from .estimate import Estimate, EstimInput
from .task import TaskModel


class Pollster:
    def knows_points(self, name: str) -> bool:
        raise NotImplementedError()

    def ask_points(self, name: str) -> EstimInput:
        raise NotImplementedError()

    def tell_points(self, name: str, points: EstimInput):
        raise NotImplementedError()

    def inform_results(self, results: typing.List[TaskModel]):
        for r in results:
            if not self.knows_points(r.name):
                continue
            estimate = self.ask_points(r.name)
            r.point_estimate = Estimate.from_triple(
                estimate.most_likely,
                estimate.optimistic,
                estimate.pessimistic)


class MemoryPollster(Pollster):
    def __init__(self):
        self._memory = dict()

    def knows_points(self, name):
        return f"{name}-points" in self._memory

    def ask_points(self, name):
        key = f"{name}-points"
        ret = self._memory.get(key, EstimInput())
        return ret

    def tell_points(self, name, points):
        key = f"{name}-points"
        self._memory[key] = points
