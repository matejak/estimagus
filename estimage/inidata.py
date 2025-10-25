import configparser
import dataclasses
import collections
import contextlib
import typing
import datetime
import pathlib
import os

from . import data, persistence
from .persistence import ini


class classproperty(property):
    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)


@dataclasses.dataclass()
class IniAppdata(persistence.ini.IniSaver, persistence.ini.IniLoader):
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

        with self._manipulate_existing_file(self.CONFIG_FILENAME) as config:
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
        config = result._load_existing_file(cls.CONFIG_FILENAME)
        result._load_retrospective_period(config)
        result._load_quarters(config)
        result._load_metadata(config)
        return result
