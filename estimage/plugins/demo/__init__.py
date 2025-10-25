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
        super().supply(obj)
        self._store_our(obj, "day_index", str(obj.day_index))
        for name, progress in obj.progress_by_id.items():
            self._store_item_attribute(f"{obj.name}-progress", name, str(progress))


@persistence.multiloader_of(DemoData, ["toml", "memory", "ini"])
class DemoLoader:
    def populate(self, ret):
        super().populate(ret)
        key = ret.name
        if key in self._loaded_data:
            ret.day_index = int(self._get_our(ret, "day_index", ret.day_index))
        key = f"{ret.name}-progress"
        if key not in self._loaded_data:
            return
        for name, progress in self._loaded_data[key].items():
            ret.progress_by_id[name] = float(progress)


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
        plugin_data = DemoData.load(self.plugin_io)
        self.day_index = plugin_data.day_index
        if self.day_index == 0:
            self.plugin_io.forget_all()
            self.cards_by_id = start(self.card_loader, self.event_io, self.start_date)

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
        plugin_data = DemoData.load(self.plugin_io)
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
                conclude_card(card, self.event_io, self.card_loader, self.start_date, plugin_data.day_index)
            else:
                begin_card(card, self.event_io, self.card_loader, self.start_date, plugin_data.day_index)

    def apply_work(self, progress, names):
        if not names:
            return
        plugin_data = DemoData.load(self.plugin_io)
        self.day_index += 1
        plugin_data.day_index = self.day_index
        if len(names) == 1 and names[0] == "noop":
            pass
        else:
            apply_velocities(names, progress, plugin_data.progress_by_id)
            self.evaluate_progress(plugin_data.progress_by_id, names, plugin_data)
        plugin_data.save(self.plugin_io)

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


def reset_data(storage_io, event_io):
    nothing = DemoData()
    nothing.save(storage_io)
    event_io.forget_all()


class NotToday:
    def get_day_index(self):
        data = DemoData.load(self.io_cls)
        return data.day_index

    @property
    def DDAY_LABEL(self):
        return f"Day {self.get_day_index() + 1}"

    def get_date_of_dday(self):
        return self.start + datetime.timedelta(days=self.get_day_index())


def start(card_loader, event_io, start_date):
    date = start_date - datetime.timedelta(days=20)

    cards_by_id = card_loader.get_loaded_cards_by_id()
    if not cards_by_id:
        predefined_cards_loader = persistence.get_persistence(data.BaseCard, "ini")
        predefined_cards_loader.LOAD_FILENAME = pathlib.Path(__file__).parent / "projective.ini"
        cards_by_id = existing_cards_loader.get_loaded_cards_by_id()

    mgr = data.EventManager()
    mgr.erase(event_io)
    for t in cards_by_id.values():
        evt = data.Event(t.name, "state", date)
        evt.value_before = "irrelevant"
        evt.value_after = "todo"
        mgr.add_event(evt)

        t.status = "todo"
        t.save_metadata(card_loader)
    mgr.save(event_io)
    return cards_by_id


def begin_card(card, event_io, card_loader, start_date, day_index):
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


def conclude_card(card, event_io, card_loader, start_date, day_index):
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
