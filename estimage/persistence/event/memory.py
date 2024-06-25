import contextlib
import typing

from ... import data


class MemoryEventsIOBase:
    _memory: typing.Dict[str, typing.List[data.Event]] = dict()

    @classmethod
    @contextlib.contextmanager
    def get_saver(cls):
        yield cls()

    @classmethod
    @contextlib.contextmanager
    def get_loader(cls):
        yield cls()


class MemoryEventsIO(MemoryEventsIOBase):
    def save_events(self, task_name: str, event_list: typing.List[data.Event]):
        self._memory[task_name] = list(event_list)

    def load_event_names(self):
        names = set(self._memory.keys())
        return names

    def load_events_of(self, name):
        return self._memory[name]

    def erase(self):
        self._memory.clear()
