import datetime
import typing

from ... import data, inidata, persistence
from .. import ini, toml, memory
from . import abstract


@persistence.saver_of(data.Event, "ini")
class IniEventsSaver(abstract.EventSaver, persistence.ini.IniSaver):
    pass

@persistence.loader_of(data.Event, "ini")
class IniEventsLoader(abstract.EventLoader, persistence.ini.IniLoader):
    pass

@persistence.saver_of(data.Event, "toml")
class TomlEventsSaver(abstract.EventSaver, persistence.toml.TomlSaver):
    pass

@persistence.loader_of(data.Event, "toml")
class TomlEventsLoader(abstract.EventLoader, persistence.toml.TomlLoader):
    pass

@persistence.saver_of(data.Event, "memory")
class MemEventsSaver(abstract.EventSaver, persistence.memory.MemSaver):
    pass

@persistence.loader_of(data.Event, "memory")
class MemEventsLoader(abstract.EventLoader, persistence.memory.MemLoader):
    pass
