import typing

from .estimate import Estimate
from .task import TaskModel
from .composition import Composition
from .card import BaseCard


class Model:
    name_result_map: typing.Mapping[str, TaskModel]
    name_composition_map: typing.Mapping[str, Composition]
    main_composition: Composition

    def __init__(self):
        self.main_composition = self._get_main_composition()
        self.name_result_map = dict()
        self.name_composition_map = dict()

    def use_composition(self, composition: Composition):
        if composition.name:
            self.main_composition = Composition("")
            self.main_composition.add_composition(composition)
        else:
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

    # TODO: strange
    def _get_new_element(self, name):
        return TaskModel(name)

    # TODO: strange - used in tests
    def new_element(self, name: str):
        e = self._get_new_element(name)
        self.add_element(e)

    # TODO: strange, why to add to the main composition?
    def add_element(self, element):
        if (name := element.name) in self.name_result_map:
            raise RuntimeError(f"Already encountered element of name {name}")
        self.name_result_map[name] = element
        return self.main_composition.add_element(element)

    def get_element(self, name):
        return self.name_result_map[name]

    def update_cards_with_values(self, cards: typing.Container[BaseCard]):
        for t in cards:
            self._update_card(t)

    def _update_card(self, card: BaseCard):
        for dep in card.children:
            self._update_card(dep)
        if card.name not in self.name_result_map:
            return
        element = self.name_result_map[card.name]
        self._update_card_by_result(card, element)

    def _update_card_by_result(self, card: BaseCard, element: TaskModel):
        pass

    # TODO: Used only in tests - redo the tests to use card update - problematic type-wise
    def export_element(self, name: str) -> BaseCard:
        card = BaseCard(name)
        self._update_card(card)
        return card


class EstiModel(Model):

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

    def _update_card_by_result(self, card: BaseCard, element: TaskModel):
        super()._update_card_by_result(card, element)
        card.point_cost = element.nominal_point_estimate.expected
        card.time_cost = element.nominal_time_estimate.expected
