import collections
import contextlib
import typing

from . import abstract
from .. import data

GLOBAL_STORAGE = collections.defaultdict(dict)


class MemSaver(abstract.Saver):
    @classmethod
    def forget_all(cls):
        global GLOBAL_STORAGE
        GLOBAL_STORAGE[cls.WHAT_IS_THIS].clear()

    def save(self):
        global GLOBAL_STORAGE
        GLOBAL_STORAGE[self.WHAT_IS_THIS].update(self._data_to_save)


class MemLoader(abstract.Loader):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._loaded_data = GLOBAL_STORAGE[self.WHAT_IS_THIS]

    @classmethod
    def get_all_card_names(cls):
        return set(GLOBAL_STORAGE[cls.WHAT_IS_THIS].keys())

    @classmethod
    def get_loaded_cards_by_id(cls, card_class=data.BaseCard):
        ret = dict()
        loader = cls()
        for name in loader._loaded_data:
            card = card_class(name)
            card.load_data_by_loader(loader)
            ret[name] = card
        return ret

    @classmethod
    @contextlib.contextmanager
    def get_loader(cls):
        yield cls()
