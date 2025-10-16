import datetime
import typing

from ... import data, inidata, persistence, PluginResolver
from .. import ini, toml, memory
from . import abstract


@PluginResolver.class_is_extendable("Storage")
class Storage:
    def save(self, saver):
        with saver.get_saver() as s:
            s.supply(self)

    @classmethod
    def load(cls, loader):
        ret = cls()
        with loader.get_loader() as l:
            l.populate(ret)
        return ret


@persistence.saver_of(Storage, "ini")
class IniEventsSaver(abstract.StorageSaver, persistence.ini.IniSaver):
    pass

@persistence.loader_of(Storage, "ini")
class IniEventsLoader(abstract.StorageLoader, persistence.ini.IniLoader):
    pass

@persistence.saver_of(Storage, "toml")
class TomlEventsSaver(abstract.StorageSaver, persistence.toml.TomlSaver):
    pass

@persistence.loader_of(Storage, "toml")
class TomlEventsLoader(abstract.StorageLoader, persistence.toml.TomlLoader):
    pass

@persistence.saver_of(Storage, "memory")
class MemEventsSaver(abstract.StorageSaver, persistence.memory.MemSaver):
    pass

@persistence.loader_of(Storage, "memory")
class MemEventsLoader(abstract.StorageLoader, persistence.memory.MemLoader):
    pass
