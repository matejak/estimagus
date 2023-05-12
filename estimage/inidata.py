import configparser
import dataclasses
import collections
import contextlib
import typing
import datetime
import pathlib

from . import data


class IniStorage:
    CONFIG_FILENAME = ""

    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)

    @staticmethod
    def _pack_list(string_list: typing.Container[str]):
        return ",".join(string_list)

    @staticmethod
    def _unpack_list(string_list: str):
        return string_list.split(",")

    @classmethod
    def _load_existing_config(cls, filename):
        config = configparser.ConfigParser(interpolation=None)
        try:
            config.read(filename)
        except configparser.MissingSectionHeaderError:
            pass
        return config

    @classmethod
    @contextlib.contextmanager
    def _manipulate_existing_config(cls, filename):
        config = cls._load_existing_config(filename)
        try:
            yield config
        finally:
            with open(filename, "w") as f:
                config.write(f)

    @contextlib.contextmanager
    def _update_key_with_dictionary(self, filename, key):
        with self._manipulate_existing_config(filename) as config:
            if key in config:
                def callback(d):
                    config[key].update(d)
            else:
                def callback(d):
                    config[key] = d
            yield callback


class IniSaverBase(IniStorage):
    WHAT_IS_THIS = "entity"

    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self._data_to_save = collections.defaultdict(dict)

    def _write_items_attribute(self, item_id, attribute_id, value):
        if not item_id:
            msg = f"Coudln't save {self.WHAT_IS_THIS}, because its name is blank."
            raise RuntimeError(msg)
        self._data_to_save[item_id][attribute_id] = value

    def save(self):
        with self._manipulate_existing_config(self.CONFIG_FILENAME) as config:
            self._save(config)

    def _save(self, all_data_to_save):
        for name, data_to_save in self._data_to_save.items():
            if name not in all_data_to_save:
                all_data_to_save[name] = dict()
            all_data_to_save[name].update(data_to_save)

    @classmethod
    @contextlib.contextmanager
    def get_saver(cls):
        saver = cls()
        yield saver
        saver.save()


class IniLoaderBase(IniStorage):
    WHAT_IS_THIS = "entity"

    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self._loaded_data = dict()

    def _read_items_attribute(self, item_id, attribute_id, fallback):
        if item_id not in self._loaded_data:
            msg = f"Couldn't load {self.WHAT_IS_THIS} '{item_id}' from '{self.CONFIG_FILENAME}'"
            raise RuntimeError(msg)
        return self._loaded_data.get(item_id, attribute_id, fallback=fallback)

    @classmethod
    @contextlib.contextmanager
    def get_loader(cls):
        loader = cls()
        loader._loaded_data = cls._load_existing_config(cls.CONFIG_FILENAME)
        yield loader


class IniPollster(data.Pollster, IniStorage):
    def _keyname(self, ns, name):
        keyname = f"{ns}-{name}"
        return keyname

    def _ask_points(self, ns, name, config=None):
        keyname = self._keyname(ns, name)

        if not config:
            config = self._load_existing_config(self.CONFIG_FILENAME)
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
            config = self._load_existing_config(self.CONFIG_FILENAME)
        if keyname in config:
            return True
        return False

    def _tell_points(self, ns, name, points: data.EstimInput):
        keyname = self._keyname(ns, name)

        with self._manipulate_existing_config(self.CONFIG_FILENAME) as config:
            config[keyname] = dict(
                most_likely=points.most_likely,
                optimistic=points.optimistic,
                pessimistic=points.pessimistic,
            )

    def _forget_points(self, ns, name):
        keyname = self._keyname(ns, name)

        with self._manipulate_existing_config(self.CONFIG_FILENAME) as config:
            config.pop(keyname)

    def provide_info_about(self, names: typing.Iterable[str], config=None) -> typing.Dict[str, data.Estimate]:
        if not config:
            config = self._load_existing_config(self.CONFIG_FILENAME)
        ret = dict()
        for name in names:
            if self._knows_points(self._namespace, name, config=config):
                ret[name] = self._ask_points(self._namespace, name, config)
        return ret


class IniEvents(data.EventManager, IniStorage):
    def save(self):
        task_names = self.get_referenced_task_names()
        with self._manipulate_existing_config(self.CONFIG_FILENAME) as config:
            for name in task_names:
                self._save_task_events(config, name, self._events[name])

    def _save_task_events(self, config, task_name: str, event_list: typing.List[data.Event]):
        all_values_to_save = dict()
        for index, event in enumerate(event_list):
            to_save = self._event_to_string_dict(event)

            keyname = f"{index:04d}-{task_name}"
            all_values_to_save[keyname] = to_save
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
            config = self._load_existing_config(self.CONFIG_FILENAME)
        events = []
        for key, value in config.items():
            if "-" in key and name == key.split("-", 1)[1]:
                event = self._get_event_from_data(value, name)
                events.append(event)
        return events

    @classmethod
    def load(cls):
        result = cls()
        config = result._load_existing_config(cls.CONFIG_FILENAME)
        for key, value in config.items():
            if "-" not in key:
                continue
            name = key.split("-", 1)[1]
            event = result._get_event_from_data(value, name)
            result._events[name].append(event)
        return result

    def _load_event_names(self, config=None):
        if config is None:
            config = self._load_existing_config(self.CONFIG_FILENAME)
        names = set()
        for key in config:
            if "-" not in key:
                continue
            names.add(key.split("-", 1)[1])
        return names


@dataclasses.dataclass()
class IniAppdata(IniStorage):
    RETROSPECTIVE_PERIOD: typing.Container[datetime.datetime] = (None, None)
    RETROSPECTIVE_QUARTER: str = ""
    PROJECTIVE_QUARTER: str = ""
    DATADIR: pathlib.Path = pathlib.Path(".")

    @classmethod
    @property
    def CONFIG_FILENAME(cls):
        ret = cls.DATADIR / cls.CONFIG_BASENAME
        return ret

    def _get_default_retrospective_period(self):
        raise NotImplementedError()

    def _get_default_projective_quarter(self):
        raise NotImplementedError()

    def _get_default_retrospective_quarter(self):
        raise NotImplementedError()

    def save(self):
        to_save = dict()
        to_save["RETROSPECTIVE_PERIOD"] = dict(
            start=self.RETROSPECTIVE_PERIOD[0],
            end=self.RETROSPECTIVE_PERIOD[1],
        )
        to_save["QUARTERS"] = dict(
            projective=self.PROJECTIVE_QUARTER,
            retrospective=self.RETROSPECTIVE_QUARTER,
        )

        with self._manipulate_existing_config(self.CONFIG_FILENAME) as config:
            config.update(to_save)

    def _load_retrospective_period(self, config):
        start = config.get("RETROSPECTIVE_PERIOD", "start", fallback=None)
        end = config.get("RETROSPECTIVE_PERIOD", "end", fallback=None)
        if start is None or end is None:
            self.RETROSPECTIVE_PERIOD = self._get_default_retrospective_period()
        else:
            self.RETROSPECTIVE_PERIOD = [datetime.datetime.fromisoformat(s) for s in (start, end)]

    def _load_quarters(self, config):
        self.PROJECTIVE_QUARTER = config.get(
            "QUARTERS", "projective", fallback=None)
        if self.PROJECTIVE_QUARTER is None:
            self.PROJECTIVE_QUARTER = self._get_default_projective_quarter()
        self.RETROSPECTIVE_QUARTER = config.get(
            "QUARTERS", "retrospective", fallback=None)
        if self.RETROSPECTIVE_QUARTER is None:
            self.RETROSPECTIVE_QUARTER = self._get_default_retrospective_quarter()

    @classmethod
    def load(cls):
        result = cls()
        config = result._load_existing_config(cls.CONFIG_FILENAME)
        result._load_retrospective_period(config)
        result._load_quarters(config)
        return result
