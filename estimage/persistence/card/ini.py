import typing
import datetime

from ... import data, inidata, persistence


class IniCardSaverBase(inidata.IniSaverBase, persistence.card.Saver):
    def _store_our(self, t, attribute, value=None):
        if value is None and hasattr(t, attribute):
            value = getattr(t, attribute)
        return self._write_items_attribute(t.name, attribute, value)


class IniCardLoaderBase(inidata.IniLoaderBase, persistence.card.Loader):
    def _get_our(self, t, attribute, fallback=None):
        if fallback is None and hasattr(t, attribute):
            fallback = getattr(t, attribute)
        return self._read_items_attribute(t.name, attribute, fallback)


@persistence.saver_of(data.BaseCard, "ini")
class IniCardSaver(IniCardSaverBase):
    def save_title_and_desc(self, t):
        self._store_our(t, "title")
        self._store_our(t, "description")

    def save_costs(self, t):
        self._store_our(t, "point_cost", str(t.point_cost))

    def save_family_records(self, t):
        depnames_str = self._pack_list([dep.name for dep in t.depends_on])
        self._store_our(t, "direct_depnames", depnames_str)
        children_str = self._pack_list([dep.name for dep in t.children])
        self._store_our(t, "depnames", children_str)
        parent_str = ""
        if t.parent:
            parent_str = t.parent.name
        self._store_our(t, "parent", parent_str)

    def save_assignee_and_collab(self, t):
        self._store_our(t, "assignee")
        collabs_str = self._pack_list(t.collaborators)
        self._store_our(t, "collaborators", collabs_str)

    def save_priority_and_status(self, t):
        self._store_our(t, "state", str(t.status))
        self._store_our(t, "priority", str(float(t.priority)))

    def save_tier(self, t):
        self._store_our(t, "tier", str(int(t.tier)))

    def save_tags(self, t):
        tags_str = self._pack_list(t.tags)
        self._store_our(t, "tags", tags_str)

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

    @classmethod
    def forget_all(cls):
        cls.erase()


@persistence.loader_of(data.BaseCard, "ini")
class IniCardLoader(IniCardLoaderBase):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._card_cache = dict()

    def load_title_and_desc(self, t):
        t.title = self._get_our(t, "title")
        t.description = self._get_our(t, "description")

    def load_costs(self, t):
        t.point_cost = float(self._get_our(t, "point_cost"))

    def _get_or_create_card_named(self, name):
        if name in self._card_cache:
            c = self._card_cache[name]
        else:
            c = self.card_class(name)
            self._card_cache[name] = c
            c.load_data_by_loader(self)
        return c

    def _load_list_of_cards_from_entry(self, t, entry_name):
        entry_contents = self._get_our(t, entry_name, "")
        all_entries = self._load_list_of_cards(entry_contents)
        return all_entries

    def _load_list_of_cards(self, list_string):
        ret = []
        for name in self._unpack_list(list_string):
            if not name:
                continue
            ret.append(self._get_or_create_card_named(name))
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
            parent = self._get_or_create_card_named(parent_id)
            t.parent = parent

    def load_assignee_and_collab(self, t):
        t.assignee = self._get_our(t, "assignee")
        t.collaborators = self._unpack_list(self._get_our(t, "collaborators"))

    def _load_status(self, t, state_name):
        t.status = inidata.get_canonical_status(state_name)

    def load_priority_and_status(self, t):
        state_name = self._get_our(t, "state")
        self._load_status(t, state_name)
        t.priority = float(self._get_our(t, "priority"))

    def load_tier(self, t):
        t.tier = int(self._get_our(t, "tier"))

    def load_tags(self, t):
        t.tags = self._unpack_list(self._get_our(t, "tags"))

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

    @classmethod
    def get_all_card_names(cls):
        config = cls._load_existing_config(cls.CONFIG_FILENAME)
        return set(config.sections())

    @classmethod
    def get_loaded_cards_by_id(cls, card_class=data.BaseCard):
        ret = dict()
        with cls.get_loader_of(card_class) as loader:
            for name in cls.get_all_card_names():
                card = card_class(name)
                card.load_data_by_loader(loader)
                ret[name] = card
        return ret

    @classmethod
    def denormalize(cls, t):
        for child in t.children:
            child.parent = t
            cls.denormalize(child)

    @classmethod
    def load_all_cards(cls, card_class=data.BaseCard):
        config = cls._load_existing_config(cls.CONFIG_FILENAME)
        ret = []
        with cls.get_loader_of(card_class) as loader:
            for name in config.sections():
                card = card_class(name)
                card.load_data_by_loader(loader)
                ret.append(card)
        return ret


class IniCardIO(IniCardSaver, IniCardLoader):
    pass
