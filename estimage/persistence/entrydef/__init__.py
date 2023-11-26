import contextlib
import typing

from ... import data


class Saver:
    @classmethod
    def bulk_save_metadata(cls, targets: typing.Iterable[data.BaseTarget]):
        saver = cls()
        for t in targets:
            t.pass_data_to_saver(saver)

    @classmethod
    def forget_all(cls):
        raise NotImplementedError()

    @classmethod
    @contextlib.contextmanager
    def get_saver(cls):
        yield cls()


class Loader:
    @classmethod
    def get_all_target_names(cls):
        raise NotImplementedError()

    @classmethod
    def get_loaded_targets_by_id(cls, target_class=typing.Type[data.BaseTarget]):
        raise NotImplementedError()

    @classmethod
    def denormalize(cls, t: data.BaseTarget):
        for child in t.children:
            child.parent = t
            cls.denormalize(child)

    @classmethod
    def load_all_targets(cls, target_class=typing.Type[data.BaseTarget]):
        raise NotImplementedError()

    @classmethod
    @contextlib.contextmanager
    def get_loader(cls):
        yield cls()
