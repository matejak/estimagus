import abc
import datetime
import typing

from ... import data, persistence
from ...persistence import toml
from . import abstract


@persistence.loader_of(data.BaseCard, "toml")
class TomlCardLoader(abstract.CardLoader, toml.TomlLoader):
    def load_basic_metadata(self, t):
        super().load_basic_metadata(t)
        t.collaborators = self._get_our(t, "collaborators")
        t.priority = float(self._get_our(t, "priority"))
        t.tags = self._get_our(t, "tags")

    def _load_list_of_cards_from_entry(self, t, entry_name):
        ret = []
        entries = self._get_our(t, entry_name, [])
        for name in entries:
            if not name:
                continue
            ret.append(self._get_loaded_or_load_card_named(t, name))
        return ret

    def load_family_records(self, t):
        all_children = self._load_list_of_cards_from_entry(t, "depnames")
        for c in all_children:
            t.add_element(c)

        all_direct_deps = self._load_list_of_cards_from_entry(t, "direct_depnames")
        for c in all_direct_deps:
            print(c)
            t.register_direct_dependency(c)

        parent_id = self._get_our(t, "parent", "")
        parent_known_notyet_fetched = parent_id and t.parent is None
        if parent_known_notyet_fetched:
            parent = self._get_loaded_or_load_card_named(t, parent_id)
            t.parent = parent

    def load_work_span(self, t):
        span = [
            self._get_our(t, "work_start", None),
            self._get_our(t, "work_end", None)]
        for index, date_str in enumerate(span):
            if date_str is not None:
                span[index] = datetime.datetime.fromisoformat(date_str)
        if span[0] or span[1]:
            t.work_span = tuple(span)

    def load_uri_and_plugin(self, t):
        t.loading_plugin = self._get_our(t, "loading_plugin")
        t.uri = self._get_our(t, "uri")


@persistence.saver_of(data.BaseCard, "toml")
class TomlCardSaver(abstract.CardSaver, toml.TomlSaver, TomlCardLoader):
    def save_basic_metadata(self, t):
        self._store_our(t, "title")
        self._store_our(t, "description")
        self._store_our(t, "point_cost", t.point_cost)
        self._store_our(t, "assignee")
        self._store_our(t, "collaborators", list(t.collaborators))
        self._store_our(t, "state", str(t.status))
        self._store_our(t, "priority", float(t.priority))
        self._store_our(t, "tier", int(t.tier))
        self._store_our(t, "tags", list(t.tags))

    def save_family_records(self, t):
        self._store_our(t, "direct_depnames", [dep.name for dep in t.depends_on])
        self._store_our(t, "depnames", [dep.name for dep in t.children])
        parent_str = ""
        if t.parent:
            parent_str = t.parent.name
        self._store_our(t, "parent", parent_str)

    def save_work_span(self, t):
        if t.work_span and t.work_span[0] is not None:
            self._store_our(t, "work_start", t.work_span[0].isoformat())
        if t.work_span and t.work_span[1] is not None:
            self._store_our(t, "work_end", t.work_span[1].isoformat())

    def save_uri_and_plugin(self, t):
        self._store_our(t, "loading_plugin")
        self._store_our(t, "uri")
