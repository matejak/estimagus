import datetime
import typing

from ... import data, persistence
from ...persistence import ini
from . import abstract


@persistence.loader_of(data.BaseCard, "ini")
class IniCardLoader(abstract.CardLoader, persistence.ini.IniLoader):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._card_cache = dict()

    def _get_all_loaded_card_names(self):
        return set(self._loaded_data.sections())

    def load_basic_metadata(self, t):
        super().load_basic_metadata(t)
        t.collaborators = self._unpack_list(self._get_our(t, "collaborators", ""))
        t.tags = self._unpack_list(self._get_our(t, "tags", ""))

    def _load_list_of_cards_from_entry(self, t, entry_name):
        entry_contents = self._get_our(t, entry_name, "")
        all_entries = self._load_list_of_cards(t, entry_contents)
        return all_entries

    def _load_list_of_cards(self, t, list_string):
        ret = []
        for name in self._unpack_list(list_string):
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


@persistence.saver_of(data.BaseCard, "ini")
class IniCardSaver(abstract.CardSaver, persistence.ini.IniSaver, IniCardLoader):
    def save_basic_metadata(self, t):
        self._store_our(t, "title")
        self._store_our(t, "description")
        self._store_our(t, "point_cost", str(t.point_cost))
        self._store_our(t, "assignee")
        collabs_str = self._pack_list(t.collaborators)
        self._store_our(t, "collaborators", collabs_str)
        self._store_our(t, "state", str(t.status))
        self._store_our(t, "priority", str(float(t.priority)))
        self._store_our(t, "tier", str(int(t.tier)))
        tags_str = self._pack_list(t.tags)
        self._store_our(t, "tags", tags_str)

    def save_family_records(self, t):
        depnames_str = self._pack_list([dep.name for dep in t.depends_on])
        self._store_our(t, "direct_depnames", depnames_str)
        children_str = self._pack_list([dep.name for dep in t.children])
        self._store_our(t, "depnames", children_str)
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

    @classmethod
    def bulk_save_metadata(cls, cards: typing.Iterable[data.BaseCard]):
        with cls.get_saver() as saver:
            for t in cards:
                t.pass_data_to_saver(saver)
