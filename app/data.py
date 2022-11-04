import re
import math
import typing
import dataclasses


class BaseTarget:
    TIME_UNIT = None
    point_cost: float
    time_cost: float
    name: str
    title: str
    description: str
    dependents: typing.List["BaseTarget"]

    def __init__(self):
        self.point_cost = 0
        self.time_cost = 0
        self.name = ""
        self.title = ""
        self.description = ""
        self.dependents = []

    def parse_point_cost(self, cost):
        return float(cost)

    def _convert_into_composition(self):
        ret = Composition(self.name)
        for d in self.dependents:
            if d.dependents:
                ret.add_composition(d.get_tree())
            else:
                ret.add_element(d.get_tree())
        return ret

    def _convert_into_single_result(self):
        ret = TaskModel(self.name)
        if self.point_cost:
            ret.point_estimate.expected = self.point_cost
        if self.time_cost:
            ret.time_estimate.expected = self.time_cost
        return ret

    def get_tree(self) -> "Composition":
        if self.dependents:
            ret = self._convert_into_composition()
        else:
            ret = self._convert_into_single_result()
        return ret

    def add_element(self, what: "BaseTarget"):
        self.dependents.append(what)

    def parse_time_cost(self, cost):
        if not self.TIME_UNIT:
            raise RuntimeError("No time estimates are expected.")
        match = re.match(rf"([0-9.]+)\s*{self.TIME_UNIT}", cost)
        if len(match.groups()) == 0:
            raise RuntimeError(f"Couldn't parse cost {cost} in units {self.TIME_UNIT}")

        return float(match.groups()[0])

    def _load_point_cost(self) -> str:
        raise NotImplementedError()

    def _load_time_cost(self) -> str:
        raise NotImplementedError()

    def load_point_cost(self):
        cost_str = self._load_point_cost()
        self.point_cost = self.parse_point_cost(cost_str)

    def load_time_cost(self):
        cost_str = self._load_time_cost()
        self.time_cost = self.parse_time_cost(cost_str)

    def _save_point_cost(self, cost_str: str):
        raise NotImplementedError()

    def _save_time_cost(self, cost_str: str):
        raise NotImplementedError()

    def save_point_cost(self):
        cost = str(int(round(self.point_cost)))
        return self._save_point_cost(cost)

    def format_time_cost(self, cost):
        cost = int(round(cost))
        return f"{cost} {self.TIME_UNIT}"

    def save_time_cost(self):
        cost = self.format_time_cost(self.time_cost)
        return self._save_time_cost(cost)

    def save_metadata(self):
        raise NotImplementedError()

    def __contains__(self, lhs: "BaseTarget"):
        lhs_name = lhs.name

        if self.name == lhs.name:
            return True

        for rhs in self.dependents:
            if rhs.name == lhs_name:
                return True
            elif lhs in rhs:
                return True
        return False

    @classmethod
    def load_metadata(cls, name: str):
        raise NotImplementedError()

    @classmethod
    def to_tree(cls, targets: typing.List["BaseTarget"]):
        if not targets:
            return Composition("")
        targets = reduce_subsets_from_sets(targets)
        if len(targets) == 1:
            return targets[0].get_tree()
        result = Composition("")
        for t in targets:
            if t.dependents:
                result.add_composition(t.get_tree())
            else:
                result.add_element(t.get_tree())
        return result


def reduce_subsets_from_sets(sets):
    reduced = []
    for index, evaluated in enumerate(sets):
        evaluated_not_contained_further = True
        for reference in sets[index + 1:]:
            if evaluated in reference:
                evaluated_not_contained_further = False
                break
        if evaluated_not_contained_further:
            reduced.append(evaluated)
    return reduced


@dataclasses.dataclass
class Estimate:
    expected: float
    sigma: float

    def __init__(self, expected, sigma):
        self.expected = expected
        self.sigma = sigma

    @classmethod
    def from_triple(cls, most_likely, optimistic, pessimistic):
        expected = (optimistic + pessimistic + 4 * most_likely) / 6
        sigma1 = math.sqrt((most_likely - optimistic) * (pessimistic - most_likely) / 7.0)
        sigma2 = (pessimistic - optimistic) / 6.0
        return cls(expected, (sigma1 + sigma2) / 2.0)

    @property
    def variance(self):
        return self.sigma ** 2

    def __add__(self, rhs):
        result = Estimate(self.expected, self.sigma)
        result.expected += rhs.expected
        result.sigma = math.sqrt(self.variance + rhs.variance)
        return result

    def rank_distance(self, estimate):
        """
        Given an estimate, return a float that
        is proportional to the differences between expected values and
        inversely proportional to the sum of standard deviations.

        If you are roughly after a value being within 2-sigma band,
        go for rank < 2, and so on
        """
        diff_of_expected = abs(estimate.expected - self.expected)
        sum_of_sigmas = estimate.sigma + self.sigma
        if diff_of_expected > 0 and sum_of_sigmas == 0:
            return float("inf")
        if diff_of_expected == 0:
            return 0
        return diff_of_expected / sum_of_sigmas


@dataclasses.dataclass(init=False)
class TaskModel:
    name: str
    time_estimate: Estimate
    point_estimate: Estimate

    def __init__(self, name):
        self.name = name
        self.nullify()

    def set_time_estimate(self, most_likely, optimistic, pessimistic):
        self.time_estimate = Estimate.from_triple(most_likely, optimistic, pessimistic)

    def set_point_estimate(self, most_likely, optimistic, pessimistic):
        self.point_estimate = Estimate.from_triple(most_likely, optimistic, pessimistic)

    def nullify(self):
        self.time_estimate = Estimate(0, 0)
        self.point_estimate = Estimate(0, 0)

    def save(self):
        raise NotImplementedError()

    @classmethod
    def load(cls, name) -> "TaskModel":
        raise NotImplementedError()


class MemoryTaskModel(TaskModel):
    RESULTS = dict()

    def save(self):
        MemoryTaskModel.RESULTS[self.name] = (
            self.point_estimate, self.time_estimate,
        )

    @classmethod
    def load(cls, name) -> "TaskModel":
        result = cls(name)
        result.point_estimate = cls.RESULTS[name][0]
        result.time_estimate = cls.RESULTS[name][1]
        return result


@dataclasses.dataclass(init=False)
class Composition:
    elements: typing.List[TaskModel]
    compositions: typing.List["Composition"]
    name: str

    def __init__(self, name):
        self.elements = []
        self.compositions = []
        self.name = name

    @property
    def time_estimate(self):
        start = Estimate(0, 0)
        for e in self.elements:
            start += e.time_estimate
        for c in self.compositions:
            start += c.time_estimate
        return start

    @property
    def point_estimate(self):
        start = Estimate(0, 0)
        for e in self.elements:
            start += e.point_estimate
        for c in self.compositions:
            start += c.point_estimate
        return start

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


class EstimInput:
    def __init__(self, value=0):
        self.optimistic = value
        self.most_likely = value
        self.pessimistic = value


class EstiModel:
    name_result_map: dict[str: TaskModel]
    name_composition_map: dict[str: Composition]
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
        self._remap_entities(self.main_composition)

    def _remap_entities(self, current_composition):
        for t in current_composition.elements:
            self.name_result_map[t.name] = t
        for c in current_composition.compositions:
            self._remap_entities(c)
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
    def point_estimate(self):
        return self.main_composition.point_estimate

    def point_estimate_of(self, name: str):
        if name in self.name_result_map:
            return self.name_result_map[name].point_estimate
        elif name in self.name_composition_map:
            return self.name_composition_map[name].point_estimate
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

    def export_element(self, name: str) -> BaseTarget:
        element = self.name_result_map[name]
        target = BaseTarget()
        target.point_cost = element.point_estimate.expected
        target.time_cost = element.time_estimate.expected
        return target


class Pollster:
    def knows_points(self, name: str) -> bool:
        raise NotImplementedError()

    def ask_points(self, name: str) -> EstimInput:
        raise NotImplementedError()

    def tell_points(self, name: str, points: EstimInput):
        raise NotImplementedError()

    def inform_results(self, results: typing.List["TaskModel"]):
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
