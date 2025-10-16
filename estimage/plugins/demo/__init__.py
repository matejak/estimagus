import pathlib
import datetime
import json
import typing

import numpy as np

from ... import data, persistence, PluginResolver
from ...persistence import local_storage, event


NULL_CHOICE = ("noop", "Do Nothing")
STORAGE_NS = ("plugins", "demo")


class DemoData(local_storage.Storage):
    def __init__(self, ** kwargs):
        self.name = "demo"
        self.day_index = 0
        self.progress_by_id = dict()


@persistence.multisaver_of(DemoData, ["toml", "memory", "ini"])
class DemoSaver:
    def supply(self, obj):
        super().supply(ret)
        self._store_our(obj, "day_index", str(obj.day_index))
        for name, progress in self.progress_by_id.items():
            self._store_item_attribute(f"{obj.name}-progress", name, str(progress))


@persistence.multiloader_of(DemoData, ["toml", "memory", "ini"])
class DemoLoader:
    def populate(self, ret):
        super().populate(ret)
        key = ret.name
        if key in self._loaded_data:
            ret.one = int(self._get_our(ret, "day_index", ret.day_index))
        key = f"{ret.name}-progress"
        if key not in self._loaded_data:
            return
        for name, progress in self._loaded_data[key].items():
            self._get_item_attribute(key, name, float(progress))


def load_data(io_cls):
    ret = DemoData.load(io_cls)
    return ret


def write_data(io_cls, storage, main, progress):
    storage.save(io_cls)


# TODO: Strategies
#  - random / uniform effort distribution
#  - flexible / lossy force usage
#  - auto-assignment of tasks (according to selection, all at once, sequential, n at a time)
#  - jump a day, jump to the end
class Demo:
    def __init__(self, start_date, card_io, plugin_io, event_io, statuses=None):
        self.card_loader = card_io
        self.plugin_io = plugin_io
        self.event_io = event_io

        self.cards_by_id = self.card_loader.get_loaded_cards_by_id()
        self.start_date = start_date
        if not statuses:
            statuses = data.Statuses()
        self.statuses = statuses

    def start_if_on_start(self):
        plugin_data = load_data(self.plugin_io)
        self.day_index = plugin_data.day_index
        if self.day_index == 0:
            start(self.cards_by_id.values(), self.card_loader, self.event_io, self.start_date)

    def get_sensible_choices(self):
        cards = self.get_ordered_wip_cards()
        sensible_choices = [(t.name, t.title) for t in cards]
        if not sensible_choices:
            sensible_choices = [NULL_CHOICE]
        return sensible_choices

    def get_ordered_wip_cards(self):
        return sorted(self.get_not_finished_cards(), key=lambda t: t.name)

    def get_actual_choices(self):
        cards = self.get_ordered_wip_cards()
        plugin_data = load_data(self.plugin_io)
        actual_choices = []
        for t in cards:
            label = f"{t.title} {plugin_data.progress_by_id.get(t.name, 0):.2g}/{t.point_cost}"
            actual_choices.append((t.name, label))
        if not actual_choices:
            actual_choices = [NULL_CHOICE]
        return actual_choices

    def evaluate_progress(self, progress_by_id, names, plugin_data):
        for name in names:
            card = self.cards_by_id[name]

            if progress_by_id[name] > card.point_cost:
                conclude_card(card, self.card_loader, self.start_date, plugin_data["day_index"])
            else:
                begin_card(card, self.card_loader, self.start_date, plugin_data["day_index"])

    def apply_work(self, progress, names):
        if not names:
            return
        plugin_data = load_data(self.plugin_io)
        self.day_index += 1
        plugin_data["day_index"] = self.day_index
        if len(names) == 1 and names[0] == "noop":
            pass
        else:
            apply_velocities(names, progress, plugin_data.progress_by_id)
            self.evaluate_progress(plugin_data.progress_by_id, names, plugin_data)
        save_data(plugin_data)

    def get_not_finished_cards(self):
        cards = self.cards_by_id.values()
        ret = [t for t in cards if self.statuses.get(t.status).relevant_and_not_done_yet]
        ret = [t for t in ret if not t.children]
        return ret


def apply_velocity(of_what, how_many, progress_by_id):
    progress_by_id[of_what] = progress_by_id.get(of_what, 0) + float(how_many)


def apply_velocities(names, progress, progress_by_id):
    proportions = np.random.rand(len(names))
    proportions *= progress / sum(proportions)
    for name, proportion in zip(names, proportions):
        apply_velocity(name, proportion, progress_by_id)


def save_data(what):
    old = load_data(self.plugin_io)
    old.update(what)

    progress = old["progress_by_id"]
    main = old
    del main["progress_by_id"]
    write_data(main, progress)


def reset_data():
    write_data(dict(), dict())


class NotToday:
    @property
    def DDAY_LABEL(self):
        data = load_data()
        day_index = data.get("day_index", 0)
        return f"Day {day_index + 1}"

    def get_date_of_dday(self):
        data = load_data()
        day_index = data.get("day_index", 0)
        return self.start + datetime.timedelta(days=day_index)


def start(cards, card_loader, event_io, start_date):
    date = start_date - datetime.timedelta(days=20)
    mgr = data.EventManager()
    mgr.erase(event_io)
    for t in cards:
        evt = data.Event(t.name, "state", date)
        evt.value_before = "irrelevant"
        evt.value_after = "todo"
        mgr.add_event(evt)

        t.status = "todo"
        t.save_metadata(card_loader)
    mgr.save(event_io)


def begin_card(card, card_loader, start_date, day_index):
    date = start_date + datetime.timedelta(days=day_index)
    mgr = data.EventManager()
    mgr.load(event_io)
    if len(mgr.get_chronological_task_events_by_type(card.name)["state"]) < 2:
        evt = data.Event(card.name, "state", date)
        evt.value_before = "todo"
        evt.value_after = "in_progress"
        mgr.add_event(evt)
        mgr.save(event_io)

    card.status = "in_progress"
    card.save_metadata(card_loader)


def conclude_card(card, card_loader, start_date, day_index):
    date = start_date + datetime.timedelta(days=day_index)
    mgr = data.EventManager()
    mgr.load(event_io)
    evt = data.Event(card.name, "state", date)
    evt.value_before = "in_progress"
    evt.value_after = "done"
    mgr.add_event(evt)
    mgr.save(event_io)

    card.status = "done"
    card.save_metadata(card_loader)


EXPORTS = dict(
    # MPLPointPlot="NotToday",
    # MPLVelocityPlot="NotToday",
    # MPLCompletionPlot="NotToday",
    Storage="DemoData",
)


TEMPLATE_OVERRIDES = {
}
