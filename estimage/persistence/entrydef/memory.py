import collections
import typing

from ... import data, persistence


GLOBAL_STORAGE = collections.defaultdict(dict)


@persistence.saver_of(data.BaseTarget, "memory")
class MemoryTargetSaver(persistence.entrydef.Saver):
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

    def save_assignee_and_collab(self, t):
        self._save(t, "assignee")
        self._save(t, "collaborators")

    def save_priority_and_state(self, t):
        self._save(t, "state")
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


@persistence.loader_of(data.BaseTarget, "memory")
class MemoryTargetLoader(persistence.entrydef.Loader):
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

    def load_assignee_and_collab(self, t):
        self._load(t, "assignee")
        self._load(t, "collaborators")

    def load_priority_and_state(self, t):
        self._load(t, "priority")
        self._load(t, "state")

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
    def get_all_target_names(cls):
        return set(GLOBAL_STORAGE.keys())

    @classmethod
    def get_loaded_targets_by_id(cls, target_class=data.BaseTarget):
        ret = dict()
        loader = cls()
        for name in GLOBAL_STORAGE:
            target = target_class(name)
            target.load_data_by_loader(loader)
            ret[name] = target
        return ret

    @classmethod
    def load_all_targets(cls, target_class=data.BaseTarget):
        ret = []
        loader = cls()
        for name in GLOBAL_STORAGE:
            target = target_class(name)
            target.load_data_by_loader(loader)
            ret.append(target)
        return ret


class MemoryTargetIO(MemoryTargetSaver, MemoryTargetLoader):
    pass
