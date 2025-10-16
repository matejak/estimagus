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


"""
@pytest.fixture
def storage_with_key_value():
    storage_in = tm.Storage()
    storage_in.feed_key("key", "value")
    return storage_in


def test_stores(storage_with_key_value):
    storage_with_key_value.feed_key("key", "val")
    assert storage_with_key_value.get_key("key") == "val"


def test_raises_exception_on_nonexistence():
    storage = tm.Storage()
    with pytest.raises(KeyError):
        assert storage.get_key("yek")


def test_is_isolated(storage_with_key_value):
    storage = tm.Storage()
    with pytest.raises(KeyError):
        assert storage.get_key("key")


@pytest.fixture(params=("memory", "ini"))
def storage_io(request, temp_filename):
    choices = dict(
        memory=tm_per.memory.GlobalMemoryIO,
        ini=tm_per.ini.IniStorageIO,
    )
    io = choices[request.param]
    io.CONFIG_FILENAME = temp_filename
    tm.Storage.erase(io)
    yield io


def test_wrong_load(storage_io):
    storage_out = tm.Storage()
    storage_out.load(storage_io)
    storage_out.request_key("ke-y")
    with pytest.raises(KeyError, match="ke-y"):
        storage_out.load(storage_io)


def test_persistence(storage_with_key_value, storage_io):
    storage_with_key_value.save(storage_io)

    storage_out = tm.Storage()
    storage_out.request_key("key")
    storage_out.load(storage_io)
    assert storage_out.get_key("key") == "value"


def test_erase(storage_with_key_value, storage_io):
    storage_with_key_value.save(storage_io)

    storage_out = tm.Storage()
    storage_out.erase(storage_io)
    storage_out.request_key("key")
    with pytest.raises(KeyError, match="key"):
        storage_out.load(storage_io)


def test_ns_key_exists(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("key", "value", namespace=("ns",))
    storage_in.feed_key("kez", "valuf", namespace=("first", "second"))
    storage_in.save(storage_io)

    storage_out = tm.Storage()
    storage_out.request_namespace(("ns",))
    storage_out.request_namespace(("first", "second"))
    storage_out.load(storage_io)
    assert storage_out.get_namespace(("ns",))["key"] == "value"
    assert storage_out.get_namespace(("first", "second"))["kez"] == "valuf"


def test_nonexistent_ns_empty_noerror(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("key", "value", namespace=("ns",))
    storage_in.save(storage_io)

    storage_out = tm.Storage()
    storage_out.request_namespace(("one", "one"))
    storage_out.request_namespace(("ns", "one"))
    storage_out.load(storage_io)
    assert not storage_out.get_namespace(("one", "one"))
    assert not storage_out.get_namespace(("ns", "one"))


def test_nonns_key_doesnt_exist(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("key", "value", namespace=("ns",))
    storage_in.save(storage_io)

    storage_out = tm.Storage()
    storage_out.request_key("key")
    with pytest.raises(KeyError, match="key"):
        storage_out.load(storage_io)


def test_ns_with_data(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("one", "1", namespace=("something", "numbers",))
    storage_in.feed_key("two", "2", namespace=("something", "numbers",))
    storage_in.save(storage_io)

    storage_out = tm.Storage()
    storage_out.request_namespace(("numbers",))
    storage_out.request_namespace(("something", "numbers",))
    storage_out.load(storage_io)
    assert not storage_out.get_namespace(("numbers",))
    numbers = storage_out.get_namespace(("something", "numbers",))
    assert len(numbers) == 2
    assert numbers["one"] == "1"
    assert numbers["two"] == "2"
    numbers["nothing"] = dict()


@pytest.fixture
def storage_with_numbers_namespace(storage_io):
    storage_in = tm.Storage()
    data = dict(One="1", two="2")
    storage_in.set_namespace(("numbers",), data)
    storage_in.save(storage_io)
    return storage_in


def test_define_ns(storage_with_numbers_namespace, storage_io):
    storage_out = tm.Storage()
    storage_out.request_namespace(("numbers",))
    storage_out.load(storage_io)
    numbers = storage_out.get_namespace(("numbers",))
    assert len(numbers) == 2
    assert numbers["One"] == "1"
    assert numbers["two"] == "2"


def test_set_ns(storage_with_numbers_namespace, storage_io):
    data = dict(two="2")
    storage_with_numbers_namespace.set_namespace(("numbers",), data)
    storage_with_numbers_namespace.save(storage_io)

    storage_out = tm.Storage()
    storage_out.request_namespace(("numbers",))
    storage_out.load(storage_io)
    numbers = storage_out.get_namespace(("numbers",))
    assert len(numbers) == 1
    assert numbers["two"] == "2"
"""
