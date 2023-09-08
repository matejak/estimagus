import dataclasses
import datetime
import typing
import collections

from . import target


@dataclasses.dataclass
class Event:
    time: datetime.datetime
    task_name: str
    quantity: str
    value_before: str
    value_after: str

    def __init__(self, task_name, quantity, time):
        self.time = time
        self.task_name = task_name
        self.quantity = quantity
        self.value_after = None
        self.value_before = None

    def __str__(self):
        return f"{self.time.date()} {self.quantity}: {self.value_before} -> {self.value_after}"

    @classmethod
    def last_points_measurement(cls, task_name, when, value):
        ret = cls(task_name, "points", when)
        ret.value_after = value
        ret.value_before = value
        return ret

    @classmethod
    def consistent(cls, events: typing.Iterable["Event"]):
        events = sorted(events, key=lambda e: e.time)
        return cls._consistent_sorted_events(events)

    @classmethod
    def _consistent_sorted_events(cls, events: typing.Iterable["Event"]):
        if len(events) < 2:
            return True
        if events[0].value_after != events[1].value_before:
            return False
        return cls._consistent_sorted_events(events[1:])


class EventManager:
    _events: typing.Dict[str, typing.List[Event]]

    def __init__(self, io_cls):
        self._events = collections.defaultdict(list)
        self._io_cls = io_cls

    def add_event(self, event: Event):
        events = self._events[event.task_name]
        events.append(event)
        self._events[event.task_name] = sorted(events, key=lambda e: e.time)

    def get_referenced_task_names(self):
        return set(self._events.keys())

    def get_chronological_task_events_by_type(self, task_name: str):
        if task_name not in self._events:
            return dict()

        sorted_events = self._events[task_name]
        events_by_type = collections.defaultdict(list)
        for evt in sorted_events:
            events_by_type[evt.quantity].append(evt)

        return events_by_type

    def save(self):
        with self._io_cls.get_saver() as saver:
            for subject_name, its_events in self._events.items():
                saver.save_events(subject_name, its_events)

    def load(self):
        with self._io_cls.get_loader() as loader:
            events_task_names = loader.load_event_names()
            for name in events_task_names:
                self._events[name] = loader.load_events_of(name)

    def erase(self):
        pass
