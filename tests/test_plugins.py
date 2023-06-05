import pytest

import estimage.plugins as tm
import estimage.plugins.null as null_plugin
from estimage import PluginResolver as to


def test_get_plugin_dynamically():
    assert tm.get_plugin("null") == null_plugin
    with pytest.raises(NameError):
        assert tm.get_plugin("nuff")


class Printer:
    OVERRIDEN = "no"

    def format(self, what):
        return what


@to.class_is_extendable("Ext")
class Extendable:
    def return_hello(self):
        return "hello"


class MockPluginWithoutDecl:
    class Formatter:
        OVERRIDEN = "maybe"


class MockPluginWithDecl(MockPluginWithoutDecl):
    EXPORTS = dict(Formatter="Formatter")


class MockPluginIncomplete:
    EXPORTS = dict(Formatter="Formatter")


@pytest.fixture
def print_plugin():
    plugin = tm.get_plugin("print_plugin", "tests")
    return plugin


def test_load_plugins(print_plugin):
    assert print_plugin.NAME == "Print"



@pytest.fixture
def resolver():
    ret = to()
    ret.add_extendable_class("Formatter", Printer)
    ret.add_known_extendable_classes()
    return ret


def test_class_resolution_sanity(resolver):
    assert "Ext" in resolver.class_dict

    cls = resolver.get_class("Formatter")
    assert cls.OVERRIDEN == "no"

    with pytest.raises(KeyError, match="Primer"):
        resolver.get_class("Primer")


def test_class_resolution_plugin_load(resolver, print_plugin):
    resolver.resolve_extension(print_plugin)

    cls = resolver.get_class("Formatter")
    assert cls.OVERRIDEN == "yes"

    resolver.resolve_extension(MockPluginWithoutDecl)
    cls = resolver.get_class("Formatter")
    assert cls.OVERRIDEN == "yes"

    instance = cls()
    assert instance.format("x") == "-x"


def test_class_resolution_mock_plugin_load(resolver):
    resolver.resolve_extension(MockPluginWithDecl)
    cls = resolver.get_class("Formatter")
    assert cls.OVERRIDEN == "maybe"

    instance = cls()
    assert instance.format("x") == "x"

    with pytest.raises(ValueError):
        resolver.resolve_extension(MockPluginIncomplete)


def test_class_extension_plugin_load(resolver, print_plugin):
    greeter = resolver.class_dict["Ext"]()
    assert greeter.return_hello() == "hello"

    resolver.resolve_extension(print_plugin)

    greeter = resolver.class_dict["Ext"]()
    assert greeter.return_hello() == "hello!"


def test_load_routes(print_plugin):
    bp = tm.get_plugin_blueprint(print_plugin)
    assert bp == "A blueprint"


def test_dont_load_routes():
    bp = tm.get_plugin_blueprint(tm)
    assert bp is None
