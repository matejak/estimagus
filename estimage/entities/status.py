import dataclasses

from .. import PluginResolver


@dataclasses.dataclass(frozen=True)
class Status:
    name: str
    relevant: bool
    wip: bool
    started: bool
    done: bool

    @classmethod
    def create(cls, name, ** kwargs):
        # Abandoned, in backlog, invalid, duplicate etc.
        relevant = kwargs.get("relevant", True)
        # In progress, work is being delivered
        wip = kwargs.get("wip", False)
        # In progress, but also stalled, in review etc.
        started = kwargs.get("started", wip)
        # not done
        done = kwargs.get("done", False)

        return cls(name=name, relevant=relevant, wip=wip, started=started, done=done)

    @property
    def relevant_and_not_done_yet(self):
        return self.relevant and not self.done

    @property
    def underway(self):
        return self.relevant and self.started and not self.done


IRRELEVANT_STATUS = Status.create("irrelevant", relevant=False)


@PluginResolver.class_is_extendable("Statuses")
class Statuses:
    def __init__(self):
        self.statuses = [
            IRRELEVANT_STATUS,
            Status.create("todo", wip=False),
            Status.create("in_progress", wip=True),
            Status.create("done", wip=False, started=True, done=True),
        ]

    def get(self, name):
        idx = self.int(name)
        if idx is None:
            msg = f"Unknown status {name}"
            raise KeyError(msg)
        return self.statuses[idx]

    def int(self, name):
        for idx, status in enumerate(self.statuses):
            if status.name == name:
                return idx

    def _statuses_have_property(self, statuses, name, value):
        ret = []
        for s in statuses:
            if getattr(s, name) == value:
                ret.append(s)
        return ret

    def that_have_properties(self, ** kwargs):
        ret = self.statuses
        for prop_name, value in kwargs.items():
            ret = self._statuses_have_property(ret, prop_name, value)
        return ret

    def get_ints(self, statuses):
        names = [s.name for s in statuses]
        ints = [self.int(n) for n in names]
        return ints
