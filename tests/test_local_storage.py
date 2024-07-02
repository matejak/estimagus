import pytest

import estimage.local_storage as tm


class MemoryIO:
    def __init__(self):
        self.storage = dict()

    def save_dict(self, data):
        self.storage.update(data)

    def load_to_dict(self, keys):
        return {key: self.storage[key] for key in keys}


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


@pytest.fixture(params=("memory",))
def storage_io(request):
    choices = dict(
        memory=MemoryIO,
    )
    io = choices[request.param]()
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


def test_namespaces(storage_io):
    storage_in = tm.Storage()
    storage_in.feed_key("key", "value", namespace=("ns",))
    storage_in.save(storage_io)

    storage_out = tm.Storage()
    storage_out.request_namespace(("ns",))
    storage_out.load(storage_io)
    assert storage_out.get_namespace(("ns",))["key"] == "value"
    storage_out.request_namespace(("one", "two"))
    storage_out.request_namespace(("one", "one"))
    storage_out.load(storage_io)
    assert not storage_out.get_namespace(("one", "one"))
    assert storage_out.get_namespace(("one", "two"))["key"] == "value"

