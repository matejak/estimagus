import re
import math
import typing
import dataclasses

import numpy as np
import scipy as sp


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


def compose_perts(pert1, pert2):
    convolution = np.convolve(pert1[1], pert2[1])
    domain = np.linspace(
        pert1[0][0] + pert2[0][0],
        pert1[0][-1] + pert2[0][-1],
        len(convolution)
    )
    return np.array([domain, convolution])


def find_arg_quantile(values, quantile):
    distfun = np.cumsum(values)
    distfun /= distfun[-1]
    distance_from_quantile = np.abs(distfun - quantile)
    index = np.argmin(distance_from_quantile)
    return index


def sink_pert(values, amount):
    new_values = values - amount
    new_values[new_values < 0] = 0
    return new_values


def pert_compute_expected_value(dom, values):
    contributions = dom * values
    imbalance = contributions.sum() / values.sum()
    return imbalance


def pert_to_estiminput(domain, values):
    for index, value in enumerate(values):
        if value > 0:
            optimistic = domain[index]
            break
    for index, value in enumerate(values[::-1]):
        if value > 0:
            pessimistic = domain[-1 - index]
            break
    most_likely_index = np.argmax(values)
    most_likely = domain[most_likely_index]
    ret = EstimInput(most_likely)
    ret.optimistic = optimistic
    ret.pessimistic = pessimistic
    return ret


def compute_estimation_from_pert(dom, values, expected, sigma):
    corresponding_input = pert_to_estiminput(dom, values)
    x0 = (corresponding_input.optimistic, corresponding_input.most_likely, corresponding_input.pessimistic)
    x0 = (corresponding_input.optimistic, corresponding_input.pessimistic)
    corr_estim = Estimate.from_input(corresponding_input)

    pert = corr_estim.get_pert(dom=dom)
    pert_autocorr = np.correlate(pert[1], pert[1])

    def objective_function(omp):
        omp = [omp[0], corresponding_input.most_likely, omp[1]]
        expected_component = (omp[0] + omp[1] * 4 + omp[2]) / 6.0 - expected
        sigma1_component = math.sqrt((omp[1] - omp[0]) * (omp[2]- omp[1]) / 7.0) - sigma
        sigma2_component = (omp[2] - omp[0]) / 6.0 - sigma
        sigma2_component = 0
        sigma_component = sigma1_component**2 + sigma2_component**2
        pert2 = Estimate.from_triple(omp[1], omp[0], omp[2]).get_pert(dom=dom)
        perts_corr = np.correlate(pert[1], pert2[1])
        divergence_component = (
            (1 - pert_autocorr / perts_corr)**2 * 1e1
            + (omp[1] - corresponding_input.most_likely) ** 2 * 0.05)
        ret = expected_component**2 * 4 + sigma_component * 1  + divergence_component
        return ret

    import scipy.optimize
    result = scipy.optimize.minimize(
        objective_function, x0,
        # method='Nelder-Mead',
        method='Powell',
        # method='COBYLA',
        bounds=[
            (x0[0], (x0[0] + corresponding_input.most_likely) / 2.0),
            ((x0[1] + corresponding_input.most_likely) / 2.0, x0[1])],
        )
    print(result)
    resulting_input = EstimInput(corresponding_input.most_likely)
    resulting_input.optimistic = result.x[0]
    resulting_input.pessimistic = result.x[1]
    ret = Estimate.from_input(resulting_input)
    print(f"expected: {expected=}, {sigma=}")
    print(f"before: {corr_estim.source}, after: {resulting_input}")
    print(f"before: {corr_estim.expected} {corr_estim.sigma}, after: {ret.expected} {ret.sigma}")
    return ret


def sink_pert_to_get_expected_value(dom, values, expected_target):
    import scipy.optimize

    current_value = pert_compute_expected_value(dom, values)
    initial_sink = values.max() * (1 - current_value / expected_target) / 20.0
    # print(f"{initial_sink=}")

    print(f"{expected_target=}")
    def objective_function(sink):
        working_values = values.copy()
        working_values = sink_pert(working_values, sink)
        # current_value = pert_compute_expected_value(dom, working_values)

        corresponding_input = pert_to_estiminput(dom, working_values)
        corresponding_expected = Estimate.from_input(corresponding_input).expected
        # print(f"{corresponding_expected=} {abs(corresponding_expected - expected_target)}")
        # return abs(current_value - expected_target) + abs(corresponding_expected - expected_target)
        ret = abs(corresponding_expected - expected_target)
        print(f"{sink=} -> {corresponding_expected=}")
        return ret

    result = scipy.optimize.minimize(
        objective_function, initial_sink,
        method='Nelder-Mead',
        # method='B'GS,
        bounds=[(0, initial_sink)],
        )
    print(result)
    values[:] = sink_pert(values, result.x)
    print (f"before: {objective_function(0)}, after: {objective_function(result.x)}")


def norm_pdf(values, dx):
    values[:] /= values.sum() * dx


@dataclasses.dataclass
class Estimate:
    expected: float
    sigma: float

    source: "EstimInput"

    def __init__(self, expected, sigma):
        self.expected = expected
        self.sigma = sigma

        self.source = None
        if self.sigma == 0:
            self.source = EstimInput(self.expected)

    @classmethod
    def from_input(cls, inp: "EstimInput"):
        ret = cls.from_triple(inp.most_likely, inp.optimistic, inp.pessimistic)
        ret.source = inp.copy()
        return ret

    @classmethod
    def from_pert(cls, domain, values):
        inp = pert_to_estiminput(domain, values)
        ret = cls.from_input(inp)
        return ret

    @classmethod
    def from_triple(cls, most_likely, optimistic, pessimistic):
        expected = (optimistic + pessimistic + 4 * most_likely) / 6
        sigma1 = math.sqrt((most_likely - optimistic) * (pessimistic - most_likely) / 7.0)
        sigma2 = (pessimistic - optimistic) / 6.0
        sigma2 = 0
        ret = cls(expected, (sigma1 + sigma2) / 2.0)
        ret.source = EstimInput(most_likely)
        ret.source.optimistic = optimistic
        ret.source.pessimistic = pessimistic
        return ret

    @property
    def variance(self):
        return self.sigma ** 2

    def __add__(self, rhs):
        result = self.compose_with(rhs)
        return result

    def get_pert_of_given_density(self, samples_per_unit=30):
        lower_bound = self.source.optimistic - 1
        upper_bound = self.source.pessimistic + 1
        dom = np.linspace(lower_bound, upper_bound, round(samples_per_unit * (upper_bound - lower_bound)))
        return self.get_pert(dom=dom)

    def get_pert(self, num_samples=100, dom=None):
        if num_samples < 1:
            msg = (
                f"Invalid sample size {num_samples} - need at least 1"
            )
            raise ValueError(msg)

        if dom is None:
            dom = np.linspace(self.source.optimistic - 1, self.source.pessimistic + 1, num_samples + 2)
            dom = dom[1:-1]
        values = self._get_pert(dom)
        if len(dom) > 1:
            norm_pdf(values, dom[1] - dom[0])
        else:
            values[0] = 1

        return np.array([dom, values])

    # TODO: Decouple composition of PERTs from fitting values on top of a PERT array.
    def compose_with(self, rhs: "Estimate", samples_per_unit=30):
        return self._compose_using_simple_values(rhs)

    def compose_using_pert_values(self, rhs: "Estimate", samples_per_unit=30):
        if self.sigma > 0 and rhs.sigma > 0:
            return self._compose_using_pert(rhs, samples_per_unit)
        else:
            return self._compose_using_shift(rhs)

    def _compose_using_simple_values(self, rhs: "Estimate"):
        ret = Estimate(self.expected, self.sigma)
        ret.expected += rhs.expected
        ret.sigma = math.sqrt(self.variance + rhs.variance)
        ret.source = None
        return ret

    def _compose_using_shift(self, rhs: "Estimate"):
        ret = Estimate.from_input(self.source)
        ret.expected += rhs.expected
        ret.sigma += rhs.sigma
        if self.source and rhs.source:
            ret.source.optimistic += rhs.source.optimistic
            ret.source.most_likely += rhs.source.most_likely
            ret.source.pessimistic += rhs.source.pessimistic
        return ret

    def _compose_using_pert(self, rhs: "Estimate", samples_per_unit=20):
        dom_len_self = round((self.source.pessimistic - self.source.optimistic) * samples_per_unit)
        dom_len_rhs = round((rhs.source.pessimistic - rhs.source.optimistic) * samples_per_unit)
        composed_pert = compose_perts(self.get_pert(dom_len_self), rhs.get_pert(dom_len_rhs))
        return composed_pert

    def produce_fit_pert(self, compose_pert):
        return compute_estimation_from_pert(composed_pert[0], composed_pert[1],
            self.expected + rhs.expected, math.sqrt(self.variance + rhs.variance))

    def _get_pert(self, domain):
        width = self.source.pessimistic - self.source.optimistic
        if width == 0:
            right_spot = np.argmin(np.abs(domain - self.source.most_likely))
            ret = np.zeros_like(domain)
            ret[right_spot] = 1.0
            return ret
        beta_a = 1 + 4 * (self.source.most_likely - self.source.optimistic) / width
        beta_b = 1 + 4 * (self.source.pessimistic - self.source.most_likely) / width
        values = sp.stats.beta.pdf(domain, beta_a, beta_b, scale=width, loc=self.source.optimistic)
        return values

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
    _time_estimate: Estimate
    _point_estimate: Estimate
    masked: bool

    def __init__(self, name):
        self.name = name
        self.nullify()
        self.masked = False

    def mask(self):
        self.masked = True

    def unmask(self):
        self.masked = False

    @property
    def time_estimate(self):
        if self.masked:
            return Estimate(0, 0)
        return self._time_estimate

    @time_estimate.setter
    def time_estimate(self, value: Estimate):
        self._time_estimate = value

    def set_time_estimate(self, most_likely, optimistic, pessimistic):
        self._time_estimate = Estimate.from_triple(most_likely, optimistic, pessimistic)

    @property
    def point_estimate(self):
        if self.masked:
            return Estimate(0, 0)
        return self._point_estimate

    @point_estimate.setter
    def point_estimate(self, value: Estimate):
        self._point_estimate = value

    def set_point_estimate(self, most_likely, optimistic, pessimistic):
        self._point_estimate = Estimate.from_triple(most_likely, optimistic, pessimistic)

    def nullify(self):
        self._time_estimate = Estimate(0, 0)
        self._point_estimate = Estimate(0, 0)

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
    def time_estimate(self):
        start = Estimate(0, 0)
        if self.masked:
            return start
        for e in self.elements:
            start += e.time_estimate
        for c in self.compositions:
            start += c.time_estimate
        return start

    @property
    def point_estimate(self):
        start = Estimate(0, 0)
        if self.masked:
            return start
        for e in self.elements:
            start += e.point_estimate
        for c in self.compositions:
            start += c.point_estimate
        return start

    def get_pert(self):
        ret = Estimate(0, 0).get_pert_of_given_density()
        for e in self.elements:
            ret = compose_perts(ret, e.get_pert_of_given_density())
        for c in self.compositions:
            ret = compose_perts(ret, c.get_pert())
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


@dataclasses.dataclass
class EstimInput:
    optimistic: float
    most_likely: float
    pessimistic: float

    def __init__(self, value=0):
        self.optimistic = value
        self.most_likely = value
        self.pessimistic = value

    def copy(self):
        ret = EstimInput(self.most_likely)
        ret.optimistic = self.optimistic
        ret.pessimistic = self.pessimistic
        return ret


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
