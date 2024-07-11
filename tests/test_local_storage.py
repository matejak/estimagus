import pytest

import estimage.local_storage as tm
import estimage.persistence.storage as tm_per

from tests.test_inidata import temp_filename


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
        memory=tm_per.memory.LocalMemoryIO,
        ini=tm_per.ini.IniStorageIO,
    )
    io = choices[request.param]
    io.CONFIG_FILENAME = temp_filename
    yield io


def test_wrong_load(storage_io):
    storage_out = tm.Storage()
    storage_out.load(storage_io())
    storage_out.request_key("ke-y")
    with pytest.raises(KeyError, match="ke-y"):
        storage_out.load(storage_io())


def test_persistence(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("key", "value")
    storage_in.save(storage_io())
    storage_out = tm.Storage()
    storage_out.request_key("key")
    storage_out.load(storage_io())
    assert storage_out.get_key("key") == "value"


def test_ns_key_exists(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("key", "value", namespace=("ns",))
    storage_in.feed_key("kez", "valuf", namespace=("first", "second"))
    storage_in.save(storage_io())

    storage_out = tm.Storage()
    storage_out.request_namespace(("ns",))
    storage_out.request_namespace(("first", "second"))
    storage_out.load(storage_io())
    assert storage_out.get_namespace(("ns",))["key"] == "value"
    assert storage_out.get_namespace(("first", "second"))["kez"] == "valuf"


def test_nonexistent_ns_empty_noerror(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("key", "value", namespace=("ns",))
    storage_in.save(storage_io())

    storage_out = tm.Storage()
    storage_out.request_namespace(("one", "one"))
    storage_out.request_namespace(("ns", "one"))
    storage_out.load(storage_io())
    assert not storage_out.get_namespace(("one", "one"))
    assert not storage_out.get_namespace(("ns", "one"))


def test_nonns_key_doesnt_exist(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("key", "value", namespace=("ns",))
    storage_in.save(storage_io())

    storage_out = tm.Storage()
    storage_out.request_key("key")
    with pytest.raises(KeyError, match="key"):
        storage_out.load(storage_io())


def test_ns_with_data(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("one", "1", namespace=("something", "numbers",))
    storage_in.feed_key("two", "2", namespace=("something", "numbers",))
    storage_in.save(storage_io())

    storage_out = tm.Storage()
    storage_out.request_namespace(("numbers",))
    storage_out.request_namespace(("something", "numbers",))
    storage_out.load(storage_io())
    assert not storage_out.get_namespace(("numbers",))
    numbers = storage_out.get_namespace(("something", "numbers",))
    assert len(numbers) == 2
    assert numbers["one"] == "1"
    assert numbers["two"] == "2"
    numbers["nothing"] = dict()


def test_define_ns(storage_io):
    storage_in = tm.Storage()
    data = dict(One="1", two="2")
    storage_in.set_namespace(("numbers",), data)
    storage_in.save(storage_io())

    storage_out = tm.Storage()
    storage_out.request_namespace(("numbers",))
    storage_out.load(storage_io())
    numbers = storage_out.get_namespace(("numbers",))
    assert len(numbers) == 2
    assert numbers["One"] == "1"
    assert numbers["two"] == "2"


def test_set_ns(storage_io):
    storage_in = tm.Storage()
    data = dict(one="1", two="3")
    storage_in.set_namespace(("numbers",), data)
    storage_in.save(storage_io())
    data = dict(two="2")
    storage_in.set_namespace(("numbers",), data)
    storage_in.save(storage_io())

    storage_out = tm.Storage()
    storage_out.request_namespace(("numbers",))
    storage_out.load(storage_io())
    numbers = storage_out.get_namespace(("numbers",))
    assert len(numbers) == 1
    assert numbers["two"] == "2"
