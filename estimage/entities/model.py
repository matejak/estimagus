import typing

from .estimate import Estimate
from .task import TaskModel
from .composition import Composition
from .target import BaseTarget


class EstiModel:
    name_result_map: typing.Mapping[str, TaskModel]
    name_composition_map: typing.Mapping[str, Composition]
    main_composition: Composition

    def __init__(self):
        self.main_composition = self._get_main_composition()
        self.name_result_map = dict()
        self.name_composition_map = dict()

    def use_composition(self, composition: Composition):
        self.main_composition = composition
        self.main_composition.name = ""

        self.name_result_map = dict()
        self.name_composition_map = dict()
        self._reconstruct_entities_map(self.main_composition)

    def _reconstruct_entities_map(self, current_composition):
        for t in current_composition.elements:
            self.name_result_map[t.name] = t
        for c in current_composition.compositions:
            self._reconstruct_entities_map(c)
            self.name_composition_map[c.name] = c

    def get_all_task_models(self):
        return list(self.name_result_map.values())

    def _get_main_composition(self):
        return Composition("")

    def _get_new_element(self, name):
        return TaskModel(name)

    def new_element(self, name: str):
        e = self._get_new_element(name)
        self.add_element(e)

    def add_element(self, element):
        if (name := element.name) in self.name_result_map:
            raise RuntimeError(f"Already encountered element of name {name}")
        self.name_result_map[name] = element
        return self.main_composition.add_element(element)

    @property
    def nominal_point_estimate(self):
        return self.main_composition.nominal_point_estimate

    @property
    def remaining_point_estimate(self):
        return self.main_composition.remaining_point_estimate

    def nominal_point_estimate_of(self, name: str) -> Estimate:
        if name in self.name_result_map:
            return self.name_result_map[name].nominal_point_estimate
        elif name in self.name_composition_map:
            return self.name_composition_map[name].nominal_point_estimate
        else:
            msg = f"Entity '{name}' is not known."
            raise KeyError(msg)

    def remaining_point_estimate_of(self, name: str) -> Estimate:
        if name in self.name_result_map:
            return self.name_result_map[name].remaining_point_estimate
        elif name in self.name_composition_map:
            return self.name_composition_map[name].remaining_point_estimate
        else:
            msg = f"Entity '{name}' is not known."
            raise KeyError(msg)

    def time_estimate_of(self, name: str):
        return self.name_result_map[name].time_estimate

    def estimate_points_of(self, name, est_input):
        self.name_result_map[name].set_point_estimate(
            est_input.most_likely, est_input.optimistic, est_input.pessimistic
        )

    def estimate_time_of(self, name, est_input):
        self.name_result_map[name].set_time_estimate(
            est_input.most_likely, est_input.optimistic, est_input.pessimistic
        )

    def complete_element(self, name):
        element = self.name_result_map[name]
        element.nullify()

    def get_element(self, name):
        return self.name_result_map[name]

    def update_targets_with_values(self, targets: typing.Container[BaseTarget]):
        for t in targets:
            self._update_target(t)

    def _update_target(self, target: BaseTarget):
        for dep in target.dependents:
            self._update_target(dep)
        if target.name not in self.name_result_map:
            return
        element = self.name_result_map[target.name]
        target.point_cost = element.nominal_point_estimate.expected
        target.time_cost = element.nominal_time_estimate.expected

    def export_element(self, name: str) -> BaseTarget:
        target = BaseTarget()
        target.name = name
        self._update_target(target)
        return target
