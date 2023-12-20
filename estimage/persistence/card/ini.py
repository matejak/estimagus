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
        depnames_str = self._pack_list([dep.name for dep in t.children])
        self._store_our(t, "depnames", depnames_str)
        parent_str = ""
        if t.parent:
            parent_str = t.parent.name
        self._store_our(t, "parent", parent_str)

    def save_assignee_and_collab(self, t):
        self._store_our(t, "assignee")
        collabs_str = self._pack_list(t.collaborators)
        self._store_our(t, "collaborators", collabs_str)

    def save_priority_and_state(self, t):
        self._store_our(t, "state", str(int(t.status)))
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
    def load_title_and_desc(self, t):
        t.title = self._get_our(t, "title")
        t.description = self._get_our(t, "description")

    def load_costs(self, t):
        t.point_cost = float(self._get_our(t, "point_cost"))

    def load_family_records(self, t):
        all_deps = self._get_our(t, "depnames", "")
        for n in self._unpack_list(all_deps):
            if not n:
                continue
            new = data.BaseCard(n)
            new.parent = t
            new.load_data_by_loader(self)
            t.add_element(new)
        parent_id = self._get_our(t, "parent", "")
        parent_known_notyet_fetched = parent_id and t.parent is None
        if parent_known_notyet_fetched:
            parent = data.BaseCard(parent_id)
            parent.load_data_by_loader(self)
            t.parent = parent

    def load_assignee_and_collab(self, t):
        t.assignee = self._get_our(t, "assignee")
        t.collaborators = self._unpack_list(self._get_our(t, "collaborators"))

    def load_priority_and_state(self, t):
        state = self._get_our(t, "state")
        t.status = data.State(int(state))
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
        with cls.get_loader() as loader:
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
        with cls.get_loader() as loader:
            for name in config.sections():
                card = card_class(name)
                card.load_data_by_loader(loader)
                ret.append(card)
        return ret


class IniCardIO(IniCardSaver, IniCardLoader):
    pass
