import abc
import datetime
import contextlib
import typing
import tomli_w, tomllib

from ... import data, inidata, persistence
from . import abstract


class FileBasedSaver(abstract.Saver):
    SAVE_FILENAME = ""
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self.save_filename = None

    def save(self):
        with self._manipulate_existing_file(self.SAVE_FILENAME) as data:
            self._save(data)

    @classmethod
    def erase(cls):
        with cls._manipulate_existing_file(cls.SAVE_FILENAME) as data:
            data.clear()

    def _save(self, all_data_to_save):
        for name, data_to_save in self._data_to_save.items():
            if name not in all_data_to_save:
                all_data_to_save[name] = dict()
            all_data_to_save[name].update(data_to_save)

    @classmethod
    @abc.abstractclassmethod
    def _manipulate_existing_file(cls):
        raise NotImplementedError()


class FileBasedLoader(abc.ABC):
    LOAD_FILENAME = ""
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._loaded_data = dict()

    def _read_items_attribute(self, item_id, attribute_id, fallback):
        if item_id not in self._loaded_data:
            msg = f"Couldn't load {self.WHAT_IS_THIS} '{item_id}' from '{self.LOAD_FILENAME}'"
            raise RuntimeError(msg)
        return self._loaded_data.get(item_id, attribute_id, fallback=fallback)

    @classmethod
    @abc.abstractclassmethod
    def _load_existing_file(cls, filename):
        raise NotImplementedError()

    @classmethod
    @contextlib.contextmanager
    def get_loader(cls):
        loader = cls()
        loader._loaded_data = cls._load_existing_file(cls.LOAD_FILENAME)
        yield loader


@persistence.loader_of(data.BaseCard, "toml")
class TomlCardLoader(abstract.CardLoader, FileBasedLoader):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._card_loading_cache = dict()

    def load_title_and_desc(self, t):
        return
        t.title = self._get_our(t, "title")
        t.description = self._get_our(t, "description")

    def load_costs(self, t):
        return
        t.point_cost = float(self._get_our(t, "point_cost"))

    def _get_or_create_card_named(self, name):
        return None
        if name in self._card_cache:
            c = self._card_cache[name]
        else:
            c = self.card_class(name)
            self._card_cache[name] = c
            c.load_data_by_loader(self)
        return c

    def _load_list_of_cards_from_entry(self, t, entry_name):
        return []
        entry_contents = self._get_our(t, entry_name, "")
        all_entries = self._load_list_of_cards(entry_contents)
        return all_entries

    def _load_list_of_cards(self, list_string):
        return []
        ret = []
        for name in self._unpack_list(list_string):
            if not name:
                continue
            ret.append(self._get_or_create_card_named(name))
        return ret

    def load_family_records(self, t):
        return
        all_children = self._load_list_of_cards_from_entry(t, "depnames")
        for c in all_children:
            t.add_element(c)

        all_direct_deps = self._load_list_of_cards_from_entry(t, "direct_depnames")
        for c in all_direct_deps:
            t.register_direct_dependency(c)

        parent_id = self._get_our(t, "parent", "")
        parent_known_notyet_fetched = parent_id and t.parent is None
        if parent_known_notyet_fetched:
            parent = self._get_or_create_card_named(parent_id)
            t.parent = parent

    def load_assignee_and_collab(self, t):
        return
        t.assignee = self._get_our(t, "assignee")
        t.collaborators = self._unpack_list(self._get_our(t, "collaborators"))

    def _load_status(self, t, state_name):
        return
        t.status = inidata.get_canonical_status(state_name)

    def load_priority_and_status(self, t):
        return
        state_name = self._get_our(t, "state")
        self._load_status(t, state_name)
        t.priority = float(self._get_our(t, "priority"))

    def load_tier(self, t):
        return
        t.tier = int(self._get_our(t, "tier"))

    def load_tags(self, t):
        return
        t.tags = self._unpack_list(self._get_our(t, "tags"))

    def load_work_span(self, t):
        return
        span = [
            self._get_our(t, "work_start", None),
            self._get_our(t, "work_end", None)]
        for index, date_str in enumerate(span):
            if date_str is not None:
                span[index] = datetime.datetime.fromisoformat(date_str)
        if span[0] or span[1]:
            t.work_span = tuple(span)

    def load_uri_and_plugin(self, t):
        return
        t.loading_plugin = self._get_our(t, "loading_plugin")
        t.uri = self._get_our(t, "uri")

    @classmethod
    def get_all_card_names(cls):
        return set()

    @classmethod
    def get_loaded_cards_by_id(cls, card_class=data.BaseCard):
        ret = dict()
        return ret

    @classmethod
    def load_all_cards(cls, card_class: typing.Type[data.BaseCard]=data.BaseCard):
        return []

    @classmethod
    def _load_existing_file(cls, filename):
        with open(filename, "rb") as f:
            config = tomllib.load(f)
        return config


@persistence.saver_of(data.BaseCard, "toml")
class TomlCardSaver(abstract.CardSaver, FileBasedSaver, TomlCardLoader):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._card_saving_cache = dict()

    def save_title_and_desc(self, t):
        self._store_our(t, "title")
        self._store_our(t, "description")

    def save_costs(self, t):
        return
        self._store_our(t, "point_cost", str(t.point_cost))

    def save_family_records(self, t):
        return
        depnames_str = self._pack_list([dep.name for dep in t.depends_on])
        self._store_our(t, "direct_depnames", depnames_str)
        children_str = self._pack_list([dep.name for dep in t.children])
        self._store_our(t, "depnames", children_str)
        parent_str = ""
        if t.parent:
            parent_str = t.parent.name
        self._store_our(t, "parent", parent_str)

    def save_assignee_and_collab(self, t):
        return
        self._store_our(t, "assignee")
        collabs_str = self._pack_list(t.collaborators)
        self._store_our(t, "collaborators", collabs_str)

    def save_priority_and_status(self, t):
        return
        self._store_our(t, "state", str(t.status))
        self._store_our(t, "priority", str(float(t.priority)))

    def save_tier(self, t):
        return
        self._store_our(t, "tier", str(int(t.tier)))

    def save_tags(self, t):
        return
        tags_str = self._pack_list(t.tags)
        self._store_our(t, "tags", tags_str)

    def save_work_span(self, t):
        return
        if t.work_span and t.work_span[0] is not None:
            self._store_our(t, "work_start", t.work_span[0].isoformat())
        if t.work_span and t.work_span[1] is not None:
            self._store_our(t, "work_end", t.work_span[1].isoformat())

    def save_uri_and_plugin(self, t):
        return
        self._store_our(t, "loading_plugin")
        self._store_our(t, "uri")

    @classmethod
    def bulk_save_metadata(cls, cards: typing.Iterable[data.BaseCard]):
        return
        with cls.get_saver() as saver:
            for t in cards:
                t.pass_data_to_saver(saver)

    @classmethod
    def forget_all(cls):
        cls.erase()

    def save(self):
        with self._manipulate_existing_file(self.SAVE_FILENAME) as config:
            self._save(config)

    @classmethod
    @contextlib.contextmanager
    def _manipulate_existing_file(cls, filename):
        config = cls._load_existing_file(filename)
        try:
            yield config
        finally:
            with open(filename, "w") as f:
                tomli_w.dump(config, f)
