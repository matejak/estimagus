import pytest

import estimage.local_storage as tm
import estimage.persistence.storage.ini as tm_ini

from tests.test_inidata import temp_filename


class MemoryIO:
    def __init__(self):
        self.storage = dict()
        self.storage[tuple()] = dict()

    def save_dict(self, data):
        self.storage.update(data)

    def load_keys_to_dict(self, keys):
        return {key: self.storage[tuple()][key] for key in keys}

    def load_ns_to_dict(self, nsname):
        return {nsname: self.storage[nsname]}


class IniIO(tm_ini.IniStorageIO):
    pass


def test_stores():
    storage = tm.Storage()
    storage.feed_key("key", "value")
    storage.feed_key("key", "val")
    assert storage.get_key("key") == "val"


def test_raises_exception_on_nonexistence():
    storage = tm.Storage()
    with pytest.raises(KeyError):
        assert storage.get_key("yek")


def test_is_isolated():
    storage = tm.Storage()
    storage.feed_key("key", "value")
    storage = tm.Storage()
    with pytest.raises(KeyError):
        assert storage.get_key("key")


def test_is_isolated():
    storage = tm.Storage()
    storage.feed_key("key", "value")
    storage = tm.Storage()
    with pytest.raises(KeyError):
        assert storage.get_key("key")


@pytest.fixture(params=("memory", "ini"))
def storage_io(request, temp_filename):
    choices = dict(
        memory=MemoryIO,
        ini=IniIO,
    )
    io = choices[request.param]()
    io.CONFIG_FILENAME = temp_filename
    yield io


def test_wrong_load(storage_io):
    storage_out = tm.Storage()
    storage_out.load(storage_io)
    storage_out.request_key("ke-y")
    with pytest.raises(KeyError, match="ke-y"):
        storage_out.load(storage_io)


def test_persistence(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("key", "value")
    storage_in.save(storage_io)
    storage_out = tm.Storage()
    storage_out.request_key("key")
    storage_out.load(storage_io)
    assert storage_out.get_key("key") == "value"


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
