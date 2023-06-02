from estimage import PluginResolver as to
from estimage import plugins

import pytest


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


def test_load_plugins():
    plugin = plugins.get_plugin("print_plugin", "tests")
    assert plugin.NAME == "Print"


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


def test_class_resolution_plugin_load(resolver):
    first_plugin = plugins.get_plugin("print_plugin", "tests")
    resolver.resolve_extension(first_plugin)

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


def test_class_extension_plugin_load(resolver):
    first_plugin = plugins.get_plugin("print_plugin", "tests")

    greeter = resolver.class_dict["Ext"]()
    assert greeter.return_hello() == "hello"

    resolver.resolve_extension(first_plugin)

    greeter = resolver.class_dict["Ext"]()
    assert greeter.return_hello() == "hello!"
