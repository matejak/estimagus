import pathlib

import datetime
import json

import flask
import numpy as np

from ... import simpledata, data


NULL_CHOICE = ("noop", "Do Nothing")


def load_data():
    try:
        with open("/tmp/estimage_demo.json") as f:
            ret = json.loads(f.read())
    except Exception:
        ret = dict()
    return ret



class Demo:
    def __init__(self, targets_by_id, loader):
        self.targets_by_id = targets_by_id
        self.loader = loader

        plugin_data = load_data()
        self.day_index = plugin_data.get("day_index", 0)
        if self.day_index == 0:
            start(targets_by_id.values(), loader)

    def get_sensible_choices(self):
        targets = self.get_ordered_wip_targets()
        sensible_choices = [(t.name, t.title) for t in targets]
        if not sensible_choices:
            sensible_choices = [NULL_CHOICE]
        return sensible_choices

    def get_ordered_wip_targets(self):
        return sorted(self.get_not_finished_targets(), key=lambda t: t.name)

    def get_actual_choices(self):
        targets = self.get_ordered_wip_targets()
        plugin_data = load_data()
        velocity_in_stash = plugin_data.get("velocity_in_stash", dict())
        label = f"{t.title} {velocity_in_stash.get(t.name, 0):.2g}/{t.point_cost}"
        actual_choices = [(t.name, label) for t in targets]
        if not actual_choices:
            actual_choices = [NULL_CHOICE]
        return actual_choices

    def evaluate_progress(self, velocity_in_stash, names, model, plugin_data):
        for name in names:
            target = self.targets_by_id[name]

            if velocity_in_stash[name] > model.remaining_point_estimate_of(name).expected:
                flask.flash(f"Finished {name}")
                conclude_target(target, self.loader, plugin_data["day_index"])
            else:
                begin_target(target, self.loader, plugin_data["day_index"])

    def apply_work(self, progress, names, model):
        plugin_data = load_data()
        self.day_index += 1
        plugin_data["day_index"] = self.day_index
        if len(names) == 1 and names[0] == "noop":
            pass
        else:
            velocity_in_stash = plugin_data.get("velocity_in_stash", dict())
            apply_velocities(names, progress, velocity_in_stash)
            plugin_data["velocity_in_stash"] = velocity_in_stash
            evaluate_progress(velocity_in_stash, names, model, plugin_data)
        save_data(plugin_data)

    def get_not_finished_targets(self):
        targets = self.targets_by_id.values()
        ret = [t for t in targets if t.state in (data.State.todo, data.State.in_progress)]
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
    mgr = simpledata.EventManager()
    pathlib.Path(mgr._io_cls.CONFIG_FILENAME).unlink(missing_ok=True)


class NotToday:
    @property
    def DDAY_LABEL(self):
        data = load_data()
        day_index = data.get("day_index", 0)
        return f"Day {day_index + 1}"

    def get_date_of_dday(self):
        data = load_data()
        day_index = data.get("day_index", 0)
        start = flask.current_app.config["RETROSPECTIVE_PERIOD"][0]
        return start + datetime.timedelta(days=day_index)


def start(targets, loader):
    start = flask.current_app.config["RETROSPECTIVE_PERIOD"][0]
    date = start - datetime.timedelta(days=20)
    mgr = simpledata.EventManager()
    for t in targets:
        evt = data.Event(t.name, "state", date)
        evt.value_before = data.State.unknown
        evt.value_after = data.State.todo
        mgr.add_event(evt)

        t.state = data.State.todo
        t.save_metadata(loader)
    mgr.save()


def begin_target(target, loader, day_index):
    start = flask.current_app.config["RETROSPECTIVE_PERIOD"][0]
    date = start + datetime.timedelta(days=day_index)
    mgr = simpledata.EventManager()
    mgr.load()
    if len(mgr.get_chronological_task_events_by_type(target.name)["state"]) < 2:
        evt = data.Event(target.name, "state", date)
        evt.value_before = data.State.todo
        evt.value_after = data.State.in_progress
        mgr.add_event(evt)
        mgr.save()

    target.state = data.State.in_progress
    target.save_metadata(loader)


def conclude_target(target, loader, day_index):
    start = flask.current_app.config["RETROSPECTIVE_PERIOD"][0]
    date = start + datetime.timedelta(days=day_index)
    mgr = simpledata.EventManager()
    mgr.load()
    evt = data.Event(target.name, "state", date)
    evt.value_before = data.State.in_progress
    evt.value_after = data.State.done
    mgr.add_event(evt)
    mgr.save()

    target.state = data.State.done
    target.save_metadata(loader)


EXPORTS = dict(
    MPLPointPlot="NotToday",
    MPLVelocityPlot="NotToday",
    MPLCompletionPlot="NotToday",
)


QUARTER_TO_MONTH_NUMBER = None
PROJECT_NAME = "OPENSCAP"


TEMPLATE_OVERRIDES = {
}
