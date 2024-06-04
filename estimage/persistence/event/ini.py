import datetime
import typing

from ... import data, inidata


class IniEventsSaver(inidata.IniSaverBase):
    def save_events(self, task_name: str, event_list: typing.List[data.Event]):
        all_values_to_save = dict()
        for index, event in enumerate(event_list):
            to_save = self._event_to_string_dict(event)

            keyname = f"{index:04d}-{task_name}"
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


class IniEventsLoader(inidata.IniLoaderBase):
    def load_event_names(self):
        names = set()
        for key in self._loaded_data:
            if "-" not in key:
                continue
            names.add(key.split("-", 1)[1])
        return names

    def load_events_of(self, name):
        events = []
        for key, value in self._loaded_data.items():
            if "-" in key and name == key.split("-", 1)[1]:
                event = self._get_event_from_data(value, name)
                events.append(event)
        return events

    def _get_event_from_data(self, data_dict, name):
        time = datetime.datetime.fromisoformat(data_dict["time"])
        ret = data.Event(name, data_dict["quantity"] or None, time)
        if "value_before" in data_dict:
            ret.value_before = data_dict["value_before"]
            if ret.quantity in ("points",):
                ret.value_before = float(ret.value_before)
            elif ret.quantity == "state":
                ret.value_before = inidata.get_canonical_status(ret.value_before)
        if "value_after" in data_dict:
            ret.value_after = data_dict["value_after"]
            if ret.quantity in ("points",):
                ret.value_after = float(ret.value_after)
            elif ret.quantity == "state":
                ret.value_after = inidata.get_canonical_status(ret.value_after)
        return ret


class IniEventsIO(IniEventsLoader, IniEventsSaver):
    pass
