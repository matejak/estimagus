import configparser
import contextlib
import typing
import datetime

from . import data


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
                collaborators=",".join(self.collaborators),
                tags=",".join(self.tags),
            )
            callback(metadata)

    @classmethod
    def get_all_target_names(cls):
        config = cls._load_existing_config()
        return set(config.sections())

    @classmethod
    def get_loaded_targets_by_id(cls):
        config = cls._load_existing_config()
        return {
            name: cls._load_metadata(name, config)
            for name in cls.get_all_target_names()
        }

    @classmethod
    def load_all_targets(cls):
        config = cls._load_existing_config()
        return [
            cls._load_metadata(name, config)
            for name in config.sections()
        ]

    @classmethod
    def load_metadata(cls, name):
        config = cls._load_existing_config()
        return cls._load_metadata(name, config)

    @classmethod
    def _load_metadata(cls, name, config):
        if name not in config:
            msg = f"{name} couldnt be loaded"
            raise RuntimeError(msg)
        ret = cls()
        ret.name = name
        ret.title = config[name].get("title", "")
        ret.description = config[name].get("description", "")
        state = config[name].get("state", data.State.unknown)
        ret.state = data.State(int(state))

        cost_str = ret._load_point_cost(config)
        ret.point_cost = ret.parse_point_cost(cost_str)

        for n in config[name].get("depnames", "").split(","):
            if not n:
                continue
            new = cls._load_metadata(n, config)
            ret.dependents.append(new)
        ret.collaborators = config[name].get("collaborators", "").split(",")
        ret.tags = set(config[name].get("tags", "").split(","))
        return ret

    def _save_point_cost(self, cost_str):
        with self._update_key_with_dictionary(self.name) as callback:
            new_value = dict(
                point_cost=cost_str,
            )
            callback(new_value)

    def _load_point_cost(self, config=None):
        if not config:
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

    def _knows_points(self, ns, name, config=None):
        keyname = self._keyname(ns, name)

        if config is None:
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

    def _forget_points(self, ns, name):
        keyname = self._keyname(ns, name)

        with self._manipulate_existing_config() as config:
            config.pop(keyname)

    def provide_info_about(self, names: typing.Iterable[str]) -> typing.Dict[str, data.Estimate]:
        config = self._load_existing_config()
        ret = dict()
        for name in names:
            if self._knows_points(self._namespace, name, config=config):
                ret[name] = self._ask_points(self._namespace, name, config)
        return ret


class IniEvents(data.EventManager, IniStorage):
    def _save_task_events(self, task_name: str, event_list: typing.List[data.Event]):
        all_values_to_save = dict()
        for index, event in enumerate(event_list):
            to_save = self._event_to_string_dict(event)

            keyname = f"{index:04d}-{task_name}"
            all_values_to_save[keyname] = to_save

        with self._manipulate_existing_config() as config:
            config.update(all_values_to_save)

    def _event_to_string_dict(self, event):
        to_save = dict(
            time=event.time.isoformat(),
            quantity=event.quantity or "",
            task_name=event.task_name
        )
        if (val := event.value_before) is not None:
            if event.quantity == "state":
                val = int(val)
            to_save["value_before"] = val
        if (val := event.value_after) is not None:
            if event.quantity == "state":
                val = int(val)
            to_save["value_after"] = val

        return to_save

    def _get_event_from_data(self, data_dict, name):
        time = datetime.datetime.fromisoformat(data_dict["time"])
        ret = data.Event(name, data_dict["quantity"] or None, time)
        if "value_before" in data_dict:
            ret.value_before = data_dict["value_before"]
            if ret.quantity in ("points",):
                ret.value_before = float(ret.value_before)
            elif ret.quantity == "state":
                ret.value_before = data.State(int(ret.value_before))
        if "value_after" in data_dict:
            ret.value_after = data_dict["value_after"]
            if ret.quantity in ("points",):
                ret.value_after = float(ret.value_after)
            elif ret.quantity == "state":
                ret.value_after = data.State(int(ret.value_after))
        return ret

    def _load_events(self, name, config=None):
        if config is None:
            config = self._load_existing_config()
        events = []
        for key, value in config.items():
            if "-" in key and name == key.split("-", 1)[1]:
                event = self._get_event_from_data(value, name)
                events.append(event)
        return events

    @classmethod
    def load(cls):
        result = cls()
        config = result._load_existing_config()
        for key, value in config.items():
            if "-" not in key:
                continue
            name = key.split("-", 1)[1]
            event = result._get_event_from_data(value, name)
            result._events[name].append(event)
        return result

    def _load_event_names(self, config=None):
        if config is None:
            config = self._load_existing_config()
        names = set()
        for key in config:
            if "-" not in key:
                continue
            names.add(key.split("-", 1)[1])
        return names
