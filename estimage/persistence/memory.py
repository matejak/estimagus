import collections
import contextlib
import typing

from . import abstract
from .. import data


class Memory:
    GLOBAL_STORAGE = collections.defaultdict(dict)


class MemSaver(abstract.Saver, Memory):
    @classmethod
    def forget_all(cls):
        cls.GLOBAL_STORAGE[cls.WHAT_IS_THIS].clear()

    def save(self):
        self.GLOBAL_STORAGE[self.WHAT_IS_THIS].update(self._data_to_save)
        for name in self._data_to_forget:
            self.GLOBAL_STORAGE[self.WHAT_IS_THIS].pop(name, None)


class MemLoader(abstract.Loader, Memory):
    def load(self):
        return self.GLOBAL_STORAGE[self.WHAT_IS_THIS]

    @classmethod
    def get_all_card_names(cls):
        return set(cls.GLOBAL_STORAGE[cls.WHAT_IS_THIS].keys())
