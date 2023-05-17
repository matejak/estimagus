import typing
import contextlib

from ... import data


class MemoryPollsterIOBase:
    _memory: typing.Dict[str, data.EstimInput] = dict()

    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)

    def _prefix(self, ns, name):
        prefix = f"{ns}-{name}"
        return prefix

    @classmethod
    @contextlib.contextmanager
    def get_saver(cls):
        yield cls()

    @classmethod
    @contextlib.contextmanager
    def get_loader(cls):
        yield cls()


class MemoryPollsterSaver(MemoryPollsterIOBase):
    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)

    def save_points(self, ns, name, points):
        prefix = self._prefix(ns, name)
        key = f"{prefix}points"
        self._memory[key] = points

    def forget_points(self, ns, name):
        prefix = self._prefix(ns, name)
        key = f"{prefix}points"
        self._memory.pop(key)


class MemoryPollsterLoader(MemoryPollsterIOBase):
    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)

    def have_points(self, ns, name):
        prefix = self._prefix(ns, name)
        return f"{prefix}points" in self._memory

    def load_points(self, ns, name):
        prefix = self._prefix(ns, name)
        key = f"{prefix}points"
        ret = self._memory.get(key, data.EstimInput())
        return ret


class MemoryPollsterIO(MemoryPollsterLoader, MemoryPollsterSaver):
    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
