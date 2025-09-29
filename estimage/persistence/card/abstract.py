import collections
import contextlib
import abc
import typing

from ... import data
from .. import abstract


class CardLoader(abstract.Loader):
    WHAT_IS_THIS = "card"
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self.card_class = kwargs.get("loaded_card_type", data.BaseCard)
        self._loaded_data = collections.defaultdict(dict)
        self._card_cache = dict()

    def _get_loaded_or_load_card_named(self, item, name):
        if name in self._card_cache:
            c = self._card_cache[name]
        else:
            c = item.__class__(name)
            self._card_cache[name] = c
            c.load_data_by_loader(self)
        return c

    @classmethod
    def denormalize(cls, t: data.BaseCard):
        for child in t.children:
            child.parent = t
            cls.denormalize(child)

    @classmethod
    @contextlib.contextmanager
    def get_loader_of(cls, loaded_card_type):
        with cls.get_loader() as ret:
            ret.card_class = loaded_card_type
            yield ret

    def _get_all_loaded_card_names(self):
        return set(self._loaded_data.keys())

    @classmethod
    def get_loaded_cards_by_id(cls, card_class=data.BaseCard):
        ret = dict()
        with cls.get_loader_of(card_class) as loader:
            loader._loaded_data = loader._load_existing_file(cls.LOAD_FILENAME)
            card_names = loader._get_all_loaded_card_names()
            for name in card_names:
                card = card_class(name)
                card.load_data_by_loader(loader)
                ret[name] = card
        return ret


class CardSaver(abstract.Saver):
    WHAT_IS_THIS = "card"
    @classmethod
    def bulk_save_metadata(cls, cards: typing.Iterable[data.BaseCard]):
        saver = cls()
        for t in cards:
            t.pass_data_to_saver(saver)

    @classmethod
    def bulk_save_metadata(cls, cards: typing.Iterable[data.BaseCard]):
        with cls.get_saver() as saver:
            for t in cards:
                t.pass_data_to_saver(saver)
