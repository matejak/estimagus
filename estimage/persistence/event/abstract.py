import abc
import collections
import datetime
import typing

from ... import data
from ...entities import status
from .. import abstract


class EventLoader(abstract.Loader):
    WHAT_IS_THIS = "event"
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._subject_to_events = collections.defaultdict(list)

    def load_events_by_subject(self):
        return self._subject_to_events

    @classmethod
    def _eventize_raw_event_data(cls, data):
        ret = collections.defaultdict(list)
        for key, event_dict in data.items():
            if "-" not in key:
                continue
            name = key.split("-", 1)[1]
            ret[name].append(cls._get_event_from_data(event_dict, name))
        return ret

    def load(self):
        ret = super().load()
        self._subject_to_events = self._eventize_raw_event_data(ret)
        return ret

    def load_events_of(self, name):
        return self._subject_to_events[name]

    @staticmethod
    def _get_event_from_data(data_dict, name):
        time = datetime.datetime.fromisoformat(data_dict["time"])
        ret = data.Event(name, data_dict["quantity"] or None, time)
        if "value_before" in data_dict:
            ret.value_before = data_dict["value_before"]
            if ret.quantity in ("points",):
                ret.value_before = float(ret.value_before)
            elif ret.quantity == "state":
                ret.value_before = status.get_canonical_status(ret.value_before)
        if "value_after" in data_dict:
            ret.value_after = data_dict["value_after"]
            if ret.quantity in ("points",):
                ret.value_after = float(ret.value_after)
            elif ret.quantity == "state":
                ret.value_after = status.get_canonical_status(ret.value_after)
        return ret


class EventSaver(abstract.Saver):
    WHAT_IS_THIS = "event"
    def save_events_by_subject(self, event_dict: typing.Dict[str, typing.Iterable[data.Event]]):
        for subject_name, events in event_dict.items():
            self._save_one_subject_events(subject_name, events)

    def _save_one_subject_events(self, subject_name: str, event_list: typing.List[data.Event]):
        all_values_to_save = dict()
        for index, event in enumerate(event_list):
            to_save = self._event_to_string_dict(event)

            keyname = f"{index:04d}-{subject_name}"
            all_values_to_save[keyname] = to_save
        self._data_to_save.update(all_values_to_save)

    def _event_to_string_dict(self, event):
        to_save = dict(
            time=event.time.isoformat(),
            quantity=event.quantity or "",
            task_name=event.task_name
        )
        if (val := event.value_before) is not None:
            to_save["value_before"] = str(val)
        if (val := event.value_after) is not None:
            to_save["value_after"] = str(val)

        return to_save
