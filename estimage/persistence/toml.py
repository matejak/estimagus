import contextlib
import tomllib

import tomli_w

from . import abstract


class TomlLoader(abstract.FileBasedLoader):
    @classmethod
    def _load_existing_file(cls, filename):
        with open(filename, "rb") as f:
            contents = tomllib.load(f)
        return contents


class TomlSaver(abstract.FileBasedSaver):
    @classmethod
    @contextlib.contextmanager
    def _manipulate_existing_file(cls, filename):
        config = cls._load_existing_file(filename)
        try:
            yield config
        finally:
            with open(filename, "wb") as f:
                tomli_w.dump(config, f)
