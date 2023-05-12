import typing

from .estimate import Estimate, EstimInput
from .task import TaskModel


class Pollster:
    namespace: str

    def __init__(self, io_cls):
        self._namespace = ""
        self._io_cls = io_cls

    def set_namespace(self, ns: str):
        self._namespace = ns

    def knows_points(self, name: str) -> bool:
        with self._io_cls.get_loader() as loader:
            return self._knows_points(loader, self._namespace, name)

    def _knows_points(self, loader, ns: str, name: str) -> bool:
        return loader.have_points(ns, name)

    def ask_points(self, name: str) -> EstimInput:
        with self._io_cls.get_loader() as loader:
            return self._ask_points(loader, self._namespace, name)

    def _ask_points(self, loader, ns: str, name: str) -> EstimInput:
        if not self._knows_points(loader, self._namespace, name):
            return EstimInput(0)
        return loader.load_points(ns, name)

    def tell_points(self, name: str, points: EstimInput):
        with self._io_cls.get_saver() as saver:
            return self._tell_points(saver, self._namespace, name, points)

    def _tell_points(self, saver, ns: str, name: str, points: EstimInput):
        return saver.save_points(ns, name, points)

    def forget_points(self, name: str):
        with self._io_cls.get_saver() as saver:
            return self._forget_points(saver, self._namespace, name)

    def _forget_points(self, saver, ns: str, name: str):
        return saver.forget_points(ns, name)

    def provide_info_about(self, names: typing.Iterable[str]) -> typing.Dict[str, Estimate]:
        ret = dict()
        with self._io_cls.get_loader() as loader:
            for name in names:
                if self._knows_points(loader, self._namespace, name):
                    ret[name] = self._ask_points(loader, self._namespace, name)
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
