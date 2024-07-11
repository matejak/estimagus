import collections
import typing

from ... import data, persistence
from . import abstract


GLOBAL_STORAGE = collections.defaultdict(dict)


@persistence.saver_of(data.BaseCard, "memory")
class MemoryCardSaver(abstract.Saver):
    def _save(self, t, attribute):
        GLOBAL_STORAGE[t.name][attribute] = getattr(t, attribute)

    def save_title_and_desc(self, t):
        self._save(t, "title")
        self._save(t, "description")

    def save_costs(self, t):
        self._save(t, "point_cost")

    def save_family_records(self, t):
        self._save(t, "children")
        self._save(t, "parent")
        self._save(t, "depends_on")

    def save_assignee_and_collab(self, t):
        self._save(t, "assignee")
        self._save(t, "collaborators")

    def save_priority_and_status(self, t):
        self._save(t, "status")
        self._save(t, "priority")

    def save_tier(self, t):
        self._save(t, "tier")

    def save_tags(self, t):
        self._save(t, "tags")

    def save_work_span(self, t):
        self._save(t, "work_span")

    def save_uri_and_plugin(self, t):
        self._save(t, "loading_plugin")
        self._save(t, "uri")

    @classmethod
    def forget_all(cls):
        GLOBAL_STORAGE.clear()


@persistence.loader_of(data.BaseCard, "memory")
class MemoryCardLoader(abstract.Loader):
    def _load(self, t, attribute):
        setattr(t, attribute, GLOBAL_STORAGE[t.name][attribute])

    def load_title_and_desc(self, t):
        self._load(t, "title")
        self._load(t, "description")

    def load_costs(self, t):
        self._load(t, "point_cost")

    def load_family_records(self, t):
        self._load(t, "children")
        self._load(t, "parent")
        self._load(t, "depends_on")

    def load_assignee_and_collab(self, t):
        self._load(t, "assignee")
        self._load(t, "collaborators")

    def load_priority_and_status(self, t):
        self._load(t, "priority")
        self._load(t, "status")

    def load_tier(self, t):
        self._load(t, "tier")

    def load_tags(self, t):
        self._load(t, "tags")

    def load_work_span(self, t):
        self._load(t, "work_span")

    def load_uri_and_plugin(self, t):
        self._load(t, "loading_plugin")
        self._load(t, "uri")

    @classmethod
    def get_all_card_names(cls):
        return set(GLOBAL_STORAGE.keys())

    @classmethod
    def get_loaded_cards_by_id(cls, card_class=data.BaseCard):
        ret = dict()
        loader = cls()
        for name in GLOBAL_STORAGE:
            card = card_class(name)
            card.load_data_by_loader(loader)
            ret[name] = card
        return ret

    @classmethod
    def load_all_cards(cls, card_class=data.BaseCard):
        ret = []
        loader = cls()
        for name in GLOBAL_STORAGE:
            card = card_class(name)
            card.load_data_by_loader(loader)
            ret.append(card)
        return ret


class MemoryCardIO(MemoryCardSaver, MemoryCardLoader):
    pass
