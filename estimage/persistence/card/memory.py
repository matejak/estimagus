import collections
import typing

from ... import data, persistence
from . import abstract
from ...persistence import memory


@persistence.saver_of(data.BaseCard, "memory")
class MemoryCardSaver(memory.MemSaver, abstract.CardSaver):
    def save_basic_metadata(self, t):
        self._store_our(t, "title")
        self._store_our(t, "description")
        self._store_our(t, "point_cost")
        self._store_our(t, "assignee")
        self._store_our(t, "collaborators")
        self._store_our(t, "status")
        self._store_our(t, "priority")
        self._store_our(t, "tier")
        self._store_our(t, "tags")

    def save_family_records(self, t):
        self._store_our(t, "children")
        self._store_our(t, "parent")
        self._store_our(t, "depends_on")

    def save_work_span(self, t):
        self._store_our(t, "work_span")

    def save_uri_and_plugin(self, t):
        self._store_our(t, "loading_plugin")
        self._store_our(t, "uri")


@persistence.loader_of(data.BaseCard, "memory")
class MemoryCardLoader(memory.MemLoader, abstract.CardLoader):
    def load_basic_metadata(self, t):
        t.title = self._get_our(t, "title")
        t.description = self._get_our(t, "description")
        t.point_cost = self._get_our(t, "point_cost")
        t.assignee = self._get_our(t, "assignee")
        t.collaborators = self._get_our(t, "collaborators")
        t.priority = self._get_our(t, "priority")
        t.status = self._get_our(t, "status")
        t.tier = self._get_our(t, "tier")
        t.tags = self._get_our(t, "tags")

    def load_family_records(self, t):
        t.children = self._get_our(t, "children")
        t.parent = self._get_our(t, "parent")
        t.depends_on = self._get_our(t, "depends_on")

    def load_work_span(self, t):
        t.work_span = self._get_our(t, "work_span")

    def load_uri_and_plugin(self, t):
        t.loading_plugin = self._get_our(t, "loading_plugin")
        t.uri = self._get_our(t, "uri")

    @classmethod
    def get_loaded_cards_by_id(cls, card_class=data.BaseCard):
        ret = dict()
        loader = cls()
        for name in loader._loaded_data:
            card = card_class(name)
            card.load_data_by_loader(loader)
            ret[name] = card
        return ret
