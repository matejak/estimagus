import re
import math
import typing


class BaseTarget:
    TIME_UNIT = None
    point_cost: float
    time_cost: float
    name: str

    def __init__(self):
        self.point_cost = 0
        self.time_cost = 0
        self.name = ""
        
    def parse_point_cost(self, cost):
        return float(cost)

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
    
    def load_time_cost(self, cost):
        cost_str = self._load_time_cost()
        self.time_cost = self.parse_time_cost(cost_str)

    def _save_point_cost(self, cost: str):
        raise NotImplementedError()

    def _save_time_cost(self, cost: str):
        raise NotImplementedError()

    def save_point_cost(self, cost):
        cost = str(int(round(cost)))
        return self._save_point_cost(cost)
    
    def format_time_cost(self, cost):
        cost = int(round(cost))
        return f"{cost} {self.TIME_UNIT}"
    
    def save_time_cost(self, cost):
        cost = self.format_time_cost(cost)
        return self._save_time_cost(cost)
    

class MemoryTarget(BaseTarget):
    def __init__(self):
        self._point_cost = ""
        self._time_cost = ""
    

class Estimate:
    def __init__(self, expected, sigma): 
        self.expected = expected
        self.sigma = sigma
        
    @classmethod
    def from_triple(cls, most_likely, optimistic, pessimistic):
        expected = (optimistic + pessimistic + 4 * most_likely) / 6
        sigma = math.sqrt((most_likely - optimistic) * (pessimistic - most_likely) / 7.0)
        return cls(expected, sigma)
    
    @property
    def variance(self):
        return self.sigma ** 2
    
    def __add__(self, rhs):
        result = Estimate(self.expected, self.sigma)
        result.expected += rhs.expected
        result.sigma = math.sqrt(self.variance + rhs.variance)
        return result
    

class Result:
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
    def load(cls, name) -> "Result":
        raise NotImplementedError()
    

class MemoryResult(Result):
    RESULTS = dict()

    def save(self):
        MemoryResult.RESULTS[self.name] = (
            self.point_estimate, self.time_estimate,
        )

    @classmethod
    def load(cls, name) -> "Result":
        result = cls(name)
        result.point_estimate = cls.RESULTS[name][0]
        result.time_estimate = cls.RESULTS[name][1]
        return result
        

class Composition:
    elements: typing.List[Result]
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
    
    def _save(self, element_names, composition_names):
        names = dict(
            elements=element_names,
            compositions=composition_names,
        )
        MemoryComposition.COMPOSITIONS[self.name] = names
    
    def _load(self):
        element_names = MemoryComposition.COMPOSITIONS[self.name]["elements"]
        for name in element_names:
            e = MemoryResult.load(name)
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
        
        
class Estimator:
    name_result_map: dict[str: Result]
    main_composition: Composition

    def __init__(self):
        self.main_composition = self._get_main_composition()
        self.name_result_map = dict()
        
    def _get_main_composition(self):
        return Composition("main")

    def _get_new_element(self, name):
        return Result(name)

    def new_element(self, name: str):
        e = self._get_new_element(name)
        self.add_element(e)
        
    def add_element(self, element):
        if (name := element.name) in self.name_result_map:
            raise RuntimeError(f"Already encountered element of name {name}")
        self.name_result_map[name] = element
        return self.main_composition.add_element(element)
    
    def point_estimate_of(self, name: str):
        return self.name_result_map[name].point_estimate
    
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
    def ask_points(self, name:str) -> EstimInput:
        raise NotImplementedError()
    
    def tell_points(self, name: str, results: EstimInput):
        raise NotImplementedError()


class MemoryPollster(Pollster):
    def __init__(self):
        self._memory = dict()

    def ask_points(self, name):
        key = f"{name}-points"
        ret = self._memory.get(key, EstimInput())
        return ret
    
    def tell_points(self, name, results):
        key = f"{name}-points"
        self._memory[key] = results