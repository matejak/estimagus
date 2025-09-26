import contextlib
import collections
import abc
import typing

from ... import data


class Saver(abc.ABC):
    WHAT_IS_THIS = ""
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._data_to_save = collections.defaultdict(dict)

    @classmethod
    @abc.abstractclassmethod
    def forget_all(cls):
        raise NotImplementedError()

    @abc.abstractclassmethod
    def save(self):
        raise NotImplementedError()

    @classmethod
    @contextlib.contextmanager
    def get_saver(cls):
        saver = cls()
        yield saver
        saver.save()


class CardSaver(Saver):
    @classmethod
    def bulk_save_metadata(cls, cards: typing.Iterable[data.BaseCard]):
        saver = cls()
        for t in cards:
            t.pass_data_to_saver(saver)

    def _store_our(self, item, attribute, value=None):
        if value is None and hasattr(item, attribute):
            value = getattr(item, attribute)
        self._data_to_save[item.name][attribute] = value


class Loader(abc.ABC):
    WHAT_IS_THIS = ""
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._loaded_data = collections.defaultdict(dict)

    @classmethod
    @abc.abstractclassmethod
    def get_all_card_names(cls):
        raise NotImplementedError()

    @classmethod
    @contextlib.contextmanager
    def get_loader(cls):
        yield cls()


class CardLoader(Loader):
    def __init__(self, ** kwargs):
        self.card_class = kwargs.get("loaded_card_type", data.BaseCard)

    @classmethod
    def denormalize(cls, t: data.BaseCard):
        for child in t.children:
            child.parent = t
            cls.denormalize(child)

    def _get_our(self, item, attribute, fallback=None):
        if fallback is None and hasattr(item, attribute):
            fallback = getattr(item, attribute)
        return self._loaded_data(item.name, attribute, fallback)

    @classmethod
    @abc.abstractmethod
    def get_loaded_cards_by_id(cls, card_class: typing.Type[data.BaseCard]=data.BaseCard):
        raise NotImplementedError()

    @classmethod
    @abc.abstractclassmethod
    def load_all_cards(cls, card_class: typing.Type[data.BaseCard]=data.BaseCard):
        raise NotImplementedError()

    @classmethod
    @contextlib.contextmanager
    def get_loader_of(cls, loaded_card_type):
        with cls.get_loader() as ret:
            ret.card_class = loaded_card_type
            yield ret
