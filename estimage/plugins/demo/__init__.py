import re
import datetime
import dataclasses
import collections
import dateutil.relativedelta
import json

from ... import simpledata, data, persistence
from .. import jira


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
        return "Week from now"

    def get_date_of_dday(self):
        data = load_data()
        day_index = data.get("day_index", 0)
        return datetime.datetime.today() + datetime.timedelta(days=day_index)


EXPORTS = dict(
    MPLPointPlot="NotToday",
    MPLVelocityPlot="NotToday",
)


QUARTER_TO_MONTH_NUMBER = None
PROJECT_NAME = "OPENSCAP"


TEMPLATE_OVERRIDES = {
}


def get_not_finished_targets(targets):
    return [t for t in targets if t.state in (data.State.todo, data.State.in_progress)]
