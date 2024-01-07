import dataclasses

from .. import PluginResolver


@dataclasses.dataclass(init=False)
class Status:
    name: str
    relevant: bool
    wip: bool
    started: bool
    done: bool

    def __init__(self, name, ** kwargs):
        self.name = name

        # Abandoned, in backlog, invalid, duplicate etc.
        self.relevant = kwargs.get("relevant", True)
        # In progress, work is being delivered
        self.wip = kwargs.get("wip", False)
        # In progress, but also stalled, in review etc.
        self.started = kwargs.get("started", self.wip)
        # not done
        self.done = kwargs.get("done", False)

    @property
    def relevant_and_not_done_yet(self):
        return self.relevant and not self.done

    @property
    def underway(self):
        return self.relevant and self.started and not self.done


IRRELEVANT_STATUS = Status("irrelevant", relevant=False)


@PluginResolver.class_is_extendable("Statuses")
class Statuses:
    def __init__(self):
        self.statuses = [
            IRRELEVANT_STATUS,
            Status("todo", wip=False),
            Status("in_progress", relevant=True, wip=True),
            Status("done", wip=False, done=True),
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
