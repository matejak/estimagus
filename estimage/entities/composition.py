import dataclasses
import typing

from .task import TaskModel, MemoryTaskModel
from .estimate import Estimate


@dataclasses.dataclass(init=False)
class Composition:
    """
    The node element in a tree of tasks.
    """
    elements: typing.List[TaskModel]
    compositions: typing.List["Composition"]
    name: str
    masked: bool

    def __init__(self, name):
        self.elements = []
        self.compositions = []
        self.name = name
        self.masked = False

    def mask(self):
        self.masked = True

    def unmask(self):
        self.masked = False

    @property
    def nominal_time_estimate(self):
        start = Estimate(0, 0)
        for e in self.elements:
            start += e.nominal_time_estimate
        for c in self.compositions:
            start += c.nominal_time_estimate
        return start

    @property
    def remaining_time_estimate(self):
        start = Estimate(0, 0)
        if self.masked:
            return start
        for e in self.elements:
            start += e.remaining_time_estimate
        for c in self.compositions:
            start += c.remaining_time_estimate
        return start

    @property
    def nominal_point_estimate(self):
        start = Estimate(0, 0)
        for e in self.elements:
            start += e.nominal_point_estimate
        for c in self.compositions:
            start += c.nominal_point_estimate
        return start

    @property
    def remaining_point_estimate(self):
        start = Estimate(0, 0)
        if self.masked:
            return start
        for e in self.elements:
            start += e.remaining_point_estimate
        for c in self.compositions:
            start += c.remaining_point_estimate
        return start

    def get_pert(self):
        starting_estimate = Estimate(0, 0)
        ret = starting_estimate.get_pert_of_given_density()
        for e in self.elements:
            ret = starting_estimate.compose_perts_of_same_scale(ret, e.get_pert_of_given_density())
        for c in self.compositions:
            ret = starting_estimate.compose_perts_of_same_scale(ret, c.get_pert())
        return ret

    def add_element(self, element):
        self.elements.append(element)

    def add_composition(self, composition):
        self.compositions.append(composition)

    def save(self):
        elements_names = list()
        compositions_names = list()
        for e in self.elements:
            e.save()
            elements_names.append(e.name)
        for c in self.compositions:
            c.save()
            compositions_names.append(c.name)
        return self._save(elements_names, compositions_names)

    def _save(self, elements_names, compositions_names):
        raise NotImplementedError()

    @classmethod
    def load(cls, name) -> "Composition":
        ret = cls(name)
        ret._load()
        return ret

    def _load(self):
        raise NotImplementedError()

    def get_contained_elements(self):
        elements = list(self.elements)
        for c in self.compositions:
            elements.extend(c.get_contained_elements())
        return elements


class MemoryComposition(Composition):
    COMPOSITIONS = dict()

    def _save(self, elements_names, compositions_names):
        names = dict(
            elements=elements_names,
            compositions=compositions_names,
        )
        MemoryComposition.COMPOSITIONS[self.name] = names

    def _load(self):
        element_names = MemoryComposition.COMPOSITIONS[self.name]["elements"]
        for name in element_names:
            e = MemoryTaskModel.load(name)
            self.elements.append(e)
        composition_names = MemoryComposition.COMPOSITIONS[self.name]["compositions"]
        for name in composition_names:
            c = MemoryComposition.load(name)
            self.compositions.append(c)
