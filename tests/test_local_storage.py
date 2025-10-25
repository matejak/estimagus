import pytest

import estimage
import estimage.persistence
import estimage.persistence.local_storage as tm

from tests.test_inidata import temp_filename, get_file_based_io


class Plugin:
    EXPORTS = dict(Storage="Storage")
    class Storage:
        def __init__(self, ** kwargs):
            self.one = 1

    @estimage.persistence.multisaver_of(Storage, ["toml", "memory", "ini"])
    class CustomSaver:
        def supply(self, obj):
            super().supply(obj)
            self._store_item_attribute("plugin", "one", str(obj.one))

    @estimage.persistence.multiloader_of(Storage, ["toml", "memory", "ini"])
    class CustomLoader:
        def populate(self, ret):
            super().populate(ret)
            ret.one = int(self._get_items_attribute("plugin", "one", ret.one))
            return ret


@pytest.fixture
def resolver():
    ret = estimage.PluginResolver()
    ret.add_known_extendable_classes()
    ret.resolve_extension(Plugin)
    return ret


@pytest.fixture
def storage_class(resolver):
    return resolver.get_final_class("Storage")


@pytest.fixture(params=("ini", "memory", "toml"))
def storage_io(request, temp_filename, storage_class):
    io = get_file_based_io(storage_class, request.param, temp_filename)
    yield io
    io.forget_all()


def test_stems(storage_class):
    io = get_file_based_io(storage_class, "ini", "")
    assert io.stem_to_filename("x") == "x.ini"
    io = get_file_based_io(storage_class, "toml", "")
    assert io.stem_to_filename("x") == "x.toml"


def test_smoke(storage_io, storage_class):
    obj = storage_class()
    assert obj.one == 1
    obj.one = 2
    obj.save(storage_io)
    loaded_obj = storage_class.load(storage_io)
    assert loaded_obj.one == 2


def test_forget(storage_io, storage_class):
    obj = storage_class()
    obj.one = 2
    obj.save(storage_io)
    storage_io.forget_all()
    loaded_obj = storage_class.load(storage_io)
    assert loaded_obj.one == 1
