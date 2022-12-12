import typing

from .estimate import Estimate, EstimInput
from .task import TaskModel


class Pollster:
    namespace: str

    def __init__(self):
        self._namespace = ""

    def set_namespace(self, ns: str):
        self._namespace = ns

    def knows_points(self, name: str) -> bool:
        return self._knows_points(self._namespace, name)

    def _knows_points(self, ns: str, name: str) -> bool:
        raise NotImplementedError()

    def ask_points(self, name: str) -> EstimInput:
        if not self.knows_points(name):
            return EstimInput(0)
        return self._ask_points(self._namespace, name)

    def _ask_points(self, ns: str, name: str) -> EstimInput:
        raise NotImplementedError()

    def tell_points(self, name: str, points: EstimInput):
        return self._tell_points(self._namespace, name, points)

    def _tell_points(self, ns: str, name: str, points: EstimInput):
        raise NotImplementedError()

    def forget_points(self, name: str):
        return self._forget_points(self._namespace, name)

    def _forget_points(self, ns: str, name: str):
        raise NotImplementedError()

    def inform_results(self, results: typing.List[TaskModel]):
        for r in results:
            if not self.knows_points(r.name):
                continue
            inp = self.ask_points(r.name)
            r.point_estimate = Estimate.from_input(inp)


class MemoryPollster(Pollster):
    _memory: typing.Dict[str, EstimInput] = dict()

    def _prefix(self, ns, name):
        prefix = f"{ns}-{name}"
        return prefix

    def _knows_points(self, ns, name):
        prefix = self._prefix(ns, name)
        return f"{prefix}points" in MemoryPollster._memory

    def _ask_points(self, ns, name):
        prefix = self._prefix(ns, name)
        key = f"{prefix}points"
        ret = MemoryPollster._memory.get(key, EstimInput())
        return ret

    def _tell_points(self, ns, name, points):
        prefix = self._prefix(ns, name)
        key = f"{prefix}points"
        MemoryPollster._memory[key] = points

    def _forget_points(self, ns, name):
        prefix = self._prefix(ns, name)
        key = f"{prefix}points"
        MemoryPollster._memory.pop(key)
