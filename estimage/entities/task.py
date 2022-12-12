import dataclasses

from .estimate import Estimate


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
        return self._time_estimate

    @time_estimate.setter
    def time_estimate(self, value: Estimate):
        self._time_estimate = value

    def set_time_estimate(self, most_likely, optimistic, pessimistic):
        self._time_estimate = Estimate.from_triple(most_likely, optimistic, pessimistic)

    @property
    def point_estimate(self):
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
