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

    def provide_info_about(self, names: typing.Iterable[str]) -> typing.Dict[str, Estimate]:
        ret = dict()
        for name in names:
            if self.knows_points(name):
                ret[name] = self.ask_points(name)
        return ret

    def supply_valid_estimations_to_tasks(self, tasks: typing.List[TaskModel]):
        tasks_by_name = {t.name: t for t in tasks}
        known_estimates = self.provide_info_about(tasks_by_name.keys())
        defective_tasks = self.supply_known_estimates_to_tasks_and_get_failed_task_names(
            known_estimates, tasks_by_name)
        if defective_tasks:
            msg = "There was a problem with following tasks: "
            msg += ", ".join(defective_tasks)
            raise ValueError(msg)

    def supply_known_estimates_to_tasks_and_get_failed_task_names(
            self, known_estimates, tasks_by_name):
        defective_tasks = set()
        for task_name, estimate_source in known_estimates.items():
            try:
                estimate = Estimate.from_input(estimate_source)
                tasks_by_name[task_name].point_estimate = estimate
            except ValueError:
                defective_tasks.add(task_name)
        return defective_tasks


class MemoryPollster(Pollster):
    _memory: typing.Dict[str, EstimInput] = dict()

    def _prefix(self, ns, name):
        prefix = f"{ns}-{name}"
        return prefix

    def _knows_points(self, ns, name):
        prefix = self._prefix(ns, name)
        return f"{prefix}points" in self._memory

    def _ask_points(self, ns, name):
        prefix = self._prefix(ns, name)
        key = f"{prefix}points"
        ret = self._memory.get(key, EstimInput())
        return ret

    def _tell_points(self, ns, name, points):
        prefix = self._prefix(ns, name)
        key = f"{prefix}points"
        self._memory[key] = points

    def _forget_points(self, ns, name):
        prefix = self._prefix(ns, name)
        key = f"{prefix}points"
        self._memory.pop(key)
