import pathlib

import datetime
import json

import numpy as np

from ... import simpledata, data, persistence


NULL_CHOICE = ("noop", "Do Nothing")


def load_data():
    try:
        with open("/tmp/estimage_demo.json") as f:
            ret = json.loads(f.read())
    except Exception:
        ret = dict()
    return ret


# TODO: Strategies
#  - random / uniform effort distribution
#  - flexible / lossy force usage
#  - auto-assignment of tasks (according to selection, all at once, sequential, n at a time)
#  - jump a day, jump to the end
class Demo:
    def __init__(self, loader, start_date, statuses=None):
        self.cards_by_id = loader.get_loaded_cards_by_id()
        self.loader = loader
        self.start_date = start_date
        if not statuses:
            statuses = data.Statuses()
        self.statuses = statuses

    def start_if_on_start(self):
        plugin_data = load_data()
        self.day_index = plugin_data.get("day_index", 0)
        if self.day_index == 0:
            start(self.cards_by_id.values(), self.loader, self.start_date)

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
        plugin_data = load_data()
        velocity_in_stash = plugin_data.get("velocity_in_stash", dict())
        actual_choices = []
        for t in cards:
            label = f"{t.title} {velocity_in_stash.get(t.name, 0):.2g}/{t.point_cost}"
            actual_choices.append((t.name, label))
        if not actual_choices:
            actual_choices = [NULL_CHOICE]
        return actual_choices

    def evaluate_progress(self, velocity_in_stash, names, plugin_data):
        for name in names:
            card = self.cards_by_id[name]

            if velocity_in_stash[name] > card.point_cost:
                previously_finished = plugin_data.get("finished", [])
                previously_finished.append(name)
                plugin_data["finished"] = previously_finished
                conclude_card(card, self.loader, self.start_date, plugin_data["day_index"])
            else:
                begin_card(card, self.loader, self.start_date, plugin_data["day_index"])

    def apply_work(self, progress, names):
        plugin_data = load_data()
        self.day_index += 1
        plugin_data["day_index"] = self.day_index
        if len(names) == 1 and names[0] == "noop":
            pass
        else:
            velocity_in_stash = plugin_data.get("velocity_in_stash", dict())
            apply_velocities(names, progress, velocity_in_stash)
            plugin_data["velocity_in_stash"] = velocity_in_stash
            self.evaluate_progress(velocity_in_stash, names, plugin_data)
        save_data(plugin_data)

    def get_not_finished_cards(self):
        cards = self.cards_by_id.values()
        ret = [t for t in cards if self.statuses.get(t.status).relevant_and_not_done_yet]
        ret = [t for t in ret if not t.children]
        return ret


def apply_velocity(of_what, how_many, velocity_in_stash):
    velocity_in_stash[of_what] = velocity_in_stash.get(of_what, 0) + float(how_many)


def apply_velocities(names, progress, velocity_in_stash):
    proportions = np.random.rand(len(names))
    proportions *= progress / sum(proportions)
    for name, proportion in zip(names, proportions):
        apply_velocity(name, proportion, velocity_in_stash)


def save_data(what):
    old = load_data()
    old.update(what)
    with open("/tmp/estimage_demo.json", "w") as f:
        json.dump(old, f)


def reset_data():
    with open("/tmp/estimage_demo.json", "w") as f:
        json.dump(dict(), f)
    io_cls = simpledata.IOs["events"]["ini"]
    pathlib.Path(io_cls.CONFIG_FILENAME).unlink(missing_ok=True)


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


def start(cards, loader, start_date):
    date = start_date - datetime.timedelta(days=20)
    mgr = data.EventManager()
    mgr.erase(simpledata.IOs["events"]["ini"])
    for t in cards:
        evt = data.Event(t.name, "state", date)
        evt.value_before = "irrelevant"
        evt.value_after = "todo"
        mgr.add_event(evt)

        t.status = "todo"
        t.save_metadata(loader)
    mgr.save(simpledata.IOs["events"]["ini"])


def begin_card(card, loader, start_date, day_index):
    date = start_date + datetime.timedelta(days=day_index)
    mgr = data.EventManager()
    mgr.load(simpledata.IOs["events"]["ini"])
    if len(mgr.get_chronological_task_events_by_type(card.name)["state"]) < 2:
        evt = data.Event(card.name, "state", date)
        evt.value_before = "todo"
        evt.value_after = "in_progress"
        mgr.add_event(evt)
        mgr.save(simpledata.IOs["events"]["ini"])

    card.status = "in_progress"
    card.save_metadata(loader)


def conclude_card(card, loader, start_date, day_index):
    date = start_date + datetime.timedelta(days=day_index)
    mgr = data.EventManager()
    mgr.load(simpledata.IOs["events"]["ini"])
    evt = data.Event(card.name, "state", date)
    evt.value_before = "in_progress"
    evt.value_after = "done"
    mgr.add_event(evt)
    mgr.save(simpledata.IOs["events"]["ini"])

    card.status = "done"
    card.save_metadata(loader)


EXPORTS = dict(
    MPLPointPlot="NotToday",
    MPLVelocityPlot="NotToday",
    MPLCompletionPlot="NotToday",
)


QUARTER_TO_MONTH_NUMBER = None
PROJECT_NAME = "OPENSCAP"


TEMPLATE_OVERRIDES = {
}
