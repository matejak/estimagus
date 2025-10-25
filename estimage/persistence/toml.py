import contextlib
import tomllib

import tomli_w

from . import abstract


class TomlBased(abstract.FileBased):
    @classmethod
    def stem_to_filename(cls, stem):
        return f"{stem}.toml"


class TomlLoader(abstract.FileBasedLoader, TomlBased):
    @classmethod
    def _load_existing_file(cls, filename):
        contents = dict()
        try:
            with open(filename, "rb") as f:
                contents = tomllib.load(f)
        except FileNotFoundError:
            pass
        return contents


class TomlSaver(abstract.FileBasedSaver, TomlBased):
    @classmethod
    @contextlib.contextmanager
    def _manipulate_existing_file(cls, filename):
        config = cls._load_existing_file(filename)
        try:
            yield config
        finally:
            with open(filename, "wb") as f:
                tomli_w.dump(config, f)
