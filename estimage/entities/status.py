import dataclasses

from .. import PluginResolver


@dataclasses.dataclass(frozen=True)
class Status:
    #: Identifiedr of the status
    name: str
    #: Abandoned, in backlog, invalid, duplicate etc. are all not relevant
    relevant: bool
    #: In progress, work is being worked on now
    wip: bool
    #: Was at least once in progress, but now can be stalled, in review etc.
    started: bool
    #: Done in the positive sense.
    done: bool

    @classmethod
    def create(cls, name, ** kwargs):
        kwargs["relevant"] = kwargs.get("relevant", True)
        kwargs["wip"] = kwargs.get("wip", False)
        kwargs["started"] = kwargs.get("started", kwargs["wip"])
        kwargs["done"] = kwargs.get("done", False)

        return cls(name=name, ** kwargs)

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
        msg = f"Status '{name}' not known."
        raise ValueError(msg)

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


def get_canonical_status(name_or_index):
    LEGACY_TABLE = [
        "irrelevant",
        "irrelevant",
        "todo",
        "in_progress",
        "in_progress",
        "done",
        "irrelevant",
    ]
    try:
        index = int(name_or_index)
        return LEGACY_TABLE[index]
    except IndexError:
        return "irrelevant"
    except ValueError:
        return name_or_index


