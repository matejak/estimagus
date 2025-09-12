import contextlib
import abc
import typing

from ... import data


class Saver(abc.ABC):
    @classmethod
    def bulk_save_metadata(cls, cards: typing.Iterable[data.BaseCard]):
        saver = cls()
        for t in cards:
            t.pass_data_to_saver(saver)

    @classmethod
    @abc.abstractclassmethod
    def forget_all(cls):
        raise NotImplementedError()

    @classmethod
    @contextlib.contextmanager
    def get_saver(cls):
        yield cls()


class Loader(abc.ABC):
    def __init__(self, ** kwargs):
        self.card_class = kwargs.get("loaded_card_type", data.BaseCard)

    @classmethod
    @abc.abstractclassmethod
    def get_all_card_names(cls):
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def get_loaded_cards_by_id(cls, card_class: typing.Type[data.BaseCard]=data.BaseCard):
        raise NotImplementedError()

    @classmethod
    def denormalize(cls, t: data.BaseCard):
        for child in t.children:
            child.parent = t
            cls.denormalize(child)

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

    @classmethod
    @contextlib.contextmanager
    def get_loader(cls):
        yield cls()
