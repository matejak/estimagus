import configparser
import contextlib
import typing

from . import abstract


class IniBased(abstract.FileBased):
    @classmethod
    def stem_to_filename(cls, stem):
        return f"{stem}.ini"


class IniLoader(abstract.FileBasedLoader, IniBased):
    @staticmethod
    def _unpack_list(string_list: str):
        return string_list.split(",")

    @classmethod
    def _load_existing_file(cls, filename):
        config = configparser.ConfigParser(interpolation=None)
        # Have keys case-sensitive: https://docs.python.org/3/library/configparser.html#id1
        config.optionxform = lambda option: option
        try:
            config.read(filename)
        except configparser.MissingSectionHeaderError:
            pass
        return config


class IniSaver(abstract.FileBasedSaver, IniBased):
    @staticmethod
    def _pack_list(string_list: typing.Container[str]):
        return ",".join(string_list)

    @classmethod
    @contextlib.contextmanager
    def _manipulate_existing_file(cls, filename):
        config = cls._load_existing_file(filename)
        try:
            yield config
        finally:
            with open(filename, "w") as f:
                config.write(f)
