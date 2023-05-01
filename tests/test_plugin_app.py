from estimage import PluginResolver as to
from estimage import plugins

import pytest


class Printer:
    OVERRIDEN = "no"

    def format(self, what):
        return what


@to.class_is_extendable("Ext")
class Extendable:
    pass


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


def test_class_resolution():
    resolver = to()
    resolver.add_overridable_class("Formatter", Printer)
    resolver.add_known_overridable_classes()
    assert "Ext" in resolver.class_dict

    cls = resolver.get_class("Formatter")
    assert cls.OVERRIDEN == "no"

    with pytest.raises(KeyError, match="Primer"):
        resolver.get_class("Primer")

    first_plugin = plugins.get_plugin("print_plugin", "tests")
    resolver.resolve_overrides(first_plugin)

    cls = resolver.get_class("Formatter")
    assert cls.OVERRIDEN == "yes"

    resolver.resolve_overrides(MockPluginWithoutDecl)
    cls = resolver.get_class("Formatter")
    assert cls.OVERRIDEN == "yes"

    instance = cls()
    assert instance.format("x") == "-x"

    resolver.resolve_overrides(MockPluginWithDecl)
    cls = resolver.get_class("Formatter")
    assert cls.OVERRIDEN == "maybe"

    resolver.resolve_overrides(MockPluginIncomplete)
