import datetime
import json

import flask

from ... import simpledata, data


def load_data():
    try:
        with open("/tmp/estimage_demo.json") as f:
            ret = json.loads(f.read())
    except Exception:
        ret = dict()
    return ret


def save_data(what):
    old = load_data()
    old.update(what)
    with open("/tmp/estimage_demo.json", "w") as f:
        json.dump(old, f)


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


def get_not_finished_targets(targets):
    ret = [t for t in targets if t.state in (data.State.todo, data.State.in_progress)]
    ret = [t for t in ret if not t.dependents]
    return ret
