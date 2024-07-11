import configparser
import dataclasses
import collections
import contextlib
import typing
import datetime
import pathlib
import os

from . import data


class classproperty(property):
    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)


def get_canonical_status(name_or_index):
    LEGACY_TABLE = [
        "irrelevant",
        "irrelevant",
        "todo",
        "in_progress",
        "in_progress",
        "done",
        "irrelevant",
    ]
    try:
        index = int(name_or_index)
        return LEGACY_TABLE[index]
    except IndexError:
        return "irrelevant"
    except ValueError:
        return name_or_index


class IniStorage:
    CONFIG_FILENAME = ""

    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

    @staticmethod
    def _pack_list(string_list: typing.Container[str]):
        return ",".join(string_list)

    @staticmethod
    def _unpack_list(string_list: str):
        return string_list.split(",")

    @classmethod
    def _load_existing_config(cls, filename):
        config = configparser.ConfigParser(interpolation=None)
        # Have keys case-sensitive: https://docs.python.org/3/library/configparser.html#id1
        config.optionxform = lambda option: option
        try:
            config.read(filename)
        except configparser.MissingSectionHeaderError:
            pass
        return config

    @classmethod
    @contextlib.contextmanager
    def _manipulate_existing_config(cls, filename):
        config = cls._load_existing_config(filename)
        try:
            yield config
        finally:
            with open(filename, "w") as f:
                config.write(f)

    @contextlib.contextmanager
    def _update_key_with_dictionary(self, filename, key):
        with self._manipulate_existing_config(filename) as config:
            if key in config:
                def callback(d):
                    config[key].update(d)
            else:
                def callback(d):
                    config[key] = d
            yield callback


class IniSaverBase(IniStorage):
    WHAT_IS_THIS = "entity"

    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._data_to_save = collections.defaultdict(dict)

    def _write_items_attribute(self, item_id, attribute_id, value):
        if not item_id:
            msg = f"Coudln't save {self.WHAT_IS_THIS}, because its name is blank."
            raise RuntimeError(msg)
        self._data_to_save[item_id][attribute_id] = value

    def save(self):
        with self._manipulate_existing_config(self.CONFIG_FILENAME) as config:
            self._save(config)

    @classmethod
    def erase(cls):
        with cls._manipulate_existing_config(cls.CONFIG_FILENAME) as config:
            config.clear()

    def _save(self, all_data_to_save):
        for name, data_to_save in self._data_to_save.items():
            if name not in all_data_to_save:
                all_data_to_save[name] = dict()
            all_data_to_save[name].update(data_to_save)

    @classmethod
    @contextlib.contextmanager
    def get_saver(cls):
        saver = cls()
        yield saver
        saver.save()


class IniLoaderBase(IniStorage):
    WHAT_IS_THIS = "entity"

    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self._loaded_data = dict()

    def _read_items_attribute(self, item_id, attribute_id, fallback):
        if item_id not in self._loaded_data:
            msg = f"Couldn't load {self.WHAT_IS_THIS} '{item_id}' from '{self.CONFIG_FILENAME}'"
            raise RuntimeError(msg)
        return self._loaded_data.get(item_id, attribute_id, fallback=fallback)

    @classmethod
    @contextlib.contextmanager
    def get_loader(cls):
        loader = cls()
        loader._loaded_data = cls._load_existing_config(cls.CONFIG_FILENAME)
        yield loader


@dataclasses.dataclass()
class IniAppdata(IniStorage):
    RETROSPECTIVE_PERIOD: typing.Container[datetime.datetime] = (None, None)
    RETROSPECTIVE_QUARTER: str = ""
    PROJECTIVE_QUARTER: str = ""
    DAY_INDEX: int = 0
    DATADIR: pathlib.Path = pathlib.Path(".")
    META: typing.Dict[str, str] = dataclasses.field(default_factory=lambda: dict())

    @classproperty
    def CONFIG_FILENAME(cls):
        ret = cls.DATADIR / cls.CONFIG_BASENAME
        return ret

    def _get_default_retrospective_period(self):
        raise NotImplementedError()

    def _get_default_projective_quarter(self):
        raise NotImplementedError()

    def _get_default_retrospective_quarter(self):
        raise NotImplementedError()

    def _save_retrospective_period(self, to_save):
        to_save["RETROSPECTIVE_PERIOD"] = dict(
            start=self.RETROSPECTIVE_PERIOD[0],
            end=self.RETROSPECTIVE_PERIOD[1],
        )

    def _save_quarters(self, to_save):
        to_save["QUARTERS"] = dict(
            projective=self.PROJECTIVE_QUARTER,
            retrospective=self.RETROSPECTIVE_QUARTER,
        )

    def _save_metadata(self, to_save):
        to_save["META"] = dict(
            description=self.META.get("description", ""),
            plugins=self.META.get("plugins_csv", ""),
        )

    def save(self):
        to_save = dict()
        self._save_retrospective_period(to_save)
        self._save_quarters(to_save)
        self._save_metadata(to_save)

        with self._manipulate_existing_config(self.CONFIG_FILENAME) as config:
            config.update(to_save)

    def _load_retrospective_period(self, config):
        start = config.get("RETROSPECTIVE_PERIOD", "start", fallback=None)
        end = config.get("RETROSPECTIVE_PERIOD", "end", fallback=None)
        if start is None or end is None:
            self.RETROSPECTIVE_PERIOD = self._get_default_retrospective_period()
        else:
            self.RETROSPECTIVE_PERIOD = [datetime.datetime.fromisoformat(s) for s in (start, end)]

    def _load_metadata(self, config):
        self.META["description"] = config.get(
            "META", "description", fallback="")
        self.META["plugins_csv"] = config.get(
            "META", "plugins", fallback="")

    def _load_quarters(self, config):
        self.PROJECTIVE_QUARTER = config.get(
            "QUARTERS", "projective", fallback=None)
        if self.PROJECTIVE_QUARTER is None:
            self.PROJECTIVE_QUARTER = self._get_default_projective_quarter()
        self.RETROSPECTIVE_QUARTER = config.get(
            "QUARTERS", "retrospective", fallback=None)
        if self.RETROSPECTIVE_QUARTER is None:
            self.RETROSPECTIVE_QUARTER = self._get_default_retrospective_quarter()

    @classmethod
    def load(cls):
        result = cls()
        config = result._load_existing_config(cls.CONFIG_FILENAME)
        result._load_retrospective_period(config)
        result._load_quarters(config)
        result._load_metadata(config)
        return result
