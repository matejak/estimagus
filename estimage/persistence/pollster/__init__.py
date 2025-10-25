import datetime
import typing

from ... import data, persistence
from ...persistence import ini, toml, memory
from . import abstract


@persistence.loader_of(data.Pollster, "ini")
class IniPollsterLoader(abstract.PollsterLoader, persistence.ini.IniLoader):
    pass


@persistence.saver_of(data.Pollster, "ini")
class IniPollsterSaver(abstract.PollsterSaver, persistence.ini.IniSaver):
    pass


@persistence.loader_of(data.Pollster, "toml")
class TomlPollsterLoader(abstract.PollsterLoader, persistence.toml.TomlLoader):
    pass


@persistence.saver_of(data.Pollster, "toml")
class IniPollsterSaver(abstract.PollsterSaver, persistence.toml.TomlSaver):
    pass


@persistence.loader_of(data.Pollster, "memory")
class TomlPollsterLoader(abstract.PollsterLoader, persistence.memory.MemLoader):
    pass


@persistence.saver_of(data.Pollster, "memory")
class IniPollsterSaver(abstract.PollsterSaver, persistence.memory.MemSaver):
    pass
