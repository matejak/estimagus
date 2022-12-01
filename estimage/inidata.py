import configparser
import contextlib
import typing
import datetime

from . import data
from . import history


class IniStorage:
    CONFIG_FILENAME = ""

    @classmethod
    def _load_existing_config(cls):
        config = configparser.ConfigParser(interpolation=None)
        try:
            config.read(cls.CONFIG_FILENAME)
        except configparser.MissingSectionHeaderError:
            pass
        return config

    @contextlib.contextmanager
    def _manipulate_existing_config(self):
        config = self._load_existing_config()
        try:
            yield config
        finally:
            with open(self.CONFIG_FILENAME, "w") as f:
                config.write(f)

    @contextlib.contextmanager
    def _update_key_with_dictionary(self, key):
        with self._manipulate_existing_config() as config:
            if key in config:
                def callback(d):
                    config[key].update(d)
            else:
                def callback(d):
                    config[key] = d
            yield callback


class IniTarget(data.BaseTarget, IniStorage):
    def save_metadata(self):
        for dep in self.dependents:
            dep.save_metadata()
        if not self.name:
            msg = "Coudln't save target, because its name is blank."
            raise RuntimeError(msg)
        with self._update_key_with_dictionary(self.name) as callback:
            metadata = dict(
                title=self.title,
                description=self.description,
                depnames=",".join([dep.name for dep in self.dependents]),
                state=str(int(self.state)),
            )
            callback(metadata)

    @classmethod
    def get_all_target_names(cls):
        config = cls._load_existing_config()
        return set(config.sections())

    @classmethod
    def get_loaded_targets_by_id(cls):
        return {
            name: cls.load_metadata(name)
            for name in cls.get_all_target_names()
        }

    @classmethod
    def load_all_targets(cls):
        config = cls._load_existing_config()
        return [
            cls.load_metadata(name)
            for name in config.sections()
        ]

    @classmethod
    def load_metadata(cls, name):
        config = cls._load_existing_config()
        if name not in config:
            msg = f"{name} couldnt be loaded"
            raise RuntimeError(msg)
        ret = cls()
        ret.name = name
        ret.title = config[name].get("title", "")
        ret.description = config[name].get("description", "")
        state = config[name].get("state", data.State.unknown)
        ret.state = data.State(int(state))
        for n in config[name].get("depnames", "").split(","):
            if not n:
                continue
            new = cls.load_metadata(n)
            ret.dependents.append(new)
        return ret

    def _save_point_cost(self, cost_str):
        with self._update_key_with_dictionary(self.name) as callback:
            new_value = dict(
                point_cost=cost_str,
            )
            callback(new_value)

    def _load_point_cost(self):
        config = self._load_existing_config()
        return config[self.name].get("point_cost", fallback=0)

    def _save_time_cost(self, cost_str):
        with self._update_key_with_dictionary(self.name) as callback:
            new_value = dict(
                time_cost=cost_str,
            )
            callback(new_value)

    def _load_time_cost(self):
        config = self._load_existing_config()
        return config[self.name].get("time_cost", fallback=0)


class IniPollster(data.Pollster, IniStorage):
    def _keyname(self, ns, name):
        keyname = f"{ns}-{name}"
        return keyname

    def _ask_points(self, ns, name):
        keyname = self._keyname(ns, name)

        config = self._load_existing_config()
        if keyname in config:
            ret = data.EstimInput()
            ret.most_likely = float(config[keyname]["most_likely"])
            ret.optimistic = float(config[keyname]["optimistic"])
            ret.pessimistic = float(config[keyname]["pessimistic"])
        else:
            ret = data.EstimInput()
        return ret

    def _knows_points(self, ns, name):
        keyname = self._keyname(ns, name)

        config = self._load_existing_config()
        if keyname in config:
            return True
        return False

    def _tell_points(self, ns, name, points: data.EstimInput):
        keyname = self._keyname(ns, name)

        with self._manipulate_existing_config() as config:
            config[keyname] = dict(
                most_likely=points.most_likely,
                optimistic=points.optimistic,
                pessimistic=points.pessimistic,
            )


class IniEvents(history.EventManager, IniStorage):
    def _save_task_events(self, task_name: str, event_list: typing.List[history.Event]):
        all_values_to_save = dict()
        for index, event in enumerate(event_list):
            to_save = dict(
                time=event.time.isoformat(),
                quantity=event.quantity or "",
                task_name=task_name
            )
            if (val := event.value_before) is not None:
                to_save["value_before"] = val
            if (val := event.value_after) is not None:
                to_save["value_after"] = val

            keyname = f"{index:04d}-{task_name}"
            all_values_to_save[keyname] = to_save

        with self._manipulate_existing_config() as config:
            config.update(all_values_to_save)

    def _get_event_from_data(self, data, name):
        time = datetime.datetime.fromisoformat(data["time"])
        ret = history.Event(name, data["quantity"] or None, time)
        if "value_before" in data:
            ret.value_before = data["value_before"]
        if "value_after" in data:
            ret.value_after = data["value_after"]
        return ret

    def _load_events(self, name):
        config = self._load_existing_config()
        events = []
        for key, value in config.items():
            if "-" in key and name == key.split("-", 1)[1]:
                event = self._get_event_from_data(value, name)
                events.append(event)
        return events

    def _load_event_names(self):
        config = self._load_existing_config()
        names = set()
        for key in config:
            if "-" not in key:
                continue
            names.add(key.split("-", 1)[1])
        return names
