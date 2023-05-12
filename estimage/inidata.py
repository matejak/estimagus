import configparser
import dataclasses
import contextlib
import typing
import datetime
import pathlib

from . import data


class IniStorage:
    CONFIG_FILENAME = ""

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


class IniTargetStateIO(IniStorage):
    def load_status_update(self, t):
        t.status_summary = self._get_our("status_summary")
        time_str = self._get_our("status_summary_time")
        if time_str:
            t.status_summary_time = datetime.datetime.fromisoformat(time_str)

    def save_status_update(self, t):
        self.data["status_summary"] = t.status_summary
        if t.status_summary_time:
            self.data["status_summary_time"] = t.status_summary_time.isoformat()


class IniTargetIO(IniTargetStateIO, IniStorage):
    def __init__(self):
        self.name = None
        self.all_data = dict()
        self.all_data = self._load_existing_config(self.CONFIG_FILENAME)
        self.data = dict()

    def _get_our(self, attribute, fallback=""):
        if self.name not in self.all_data:
            raise RuntimeError(f"Couldn't load '{self.name}' from '{self.CONFIG_FILENAME}'")
        return self.all_data.get(self.name, attribute, fallback=fallback)

    def load_name_title_and_desc(self, t):
        t.name = self.name
        t.title = self._get_our("title")
        t.description = self._get_our("description")

    def load_costs(self, t):
        t.point_cost = float(self._get_our("point_cost", 0))

    def load_dependents(self, t):
        all_deps = self._get_our("depnames")
        original_name = self.name
        for n in self._unpack_list(all_deps):
            if not n:
                continue
            self.name = n
            new = t.load_metadata(n, self.__class__)
            t.dependents.append(new)
        self.name = original_name

    def load_assignee_and_collab(self, t):
        t.assignee = self._get_our("assignee")
        t.collaborators = self._unpack_list(self._get_our("collaborators"))

    def load_priority_and_state(self, t):
        state = self._get_our("state", data.State.unknown)
        t.state = data.State(int(state))
        t.priority = float(self._get_our("priority", t.priority))

    def load_tier(self, t):
        t.tier = int(self._get_our("tier", t.tier))

    def load_tags(self, t):
        t.tags = self._unpack_list(self._get_our("tags"))

    def load_work_span(self, t):
        span = [
            self._get_our("work_start", None),
            self._get_our("work_end", None)]
        for index, date_str in enumerate(span):
            if date_str is not None:
                span[index] = datetime.datetime.fromisoformat(date_str)
        if span[0] or span[1]:
            t.work_span = tuple(span)

    def load_uri_and_plugin(self, t):
        t.loading_plugin = self._get_our("loading_plugin", t.loading_plugin)
        t.uri = self._get_our("uri", t.uri)

    def save_name_title_and_desc(self, t):
        if not t.name:
            msg = "Coudln't save target, because its name is blank."
            raise RuntimeError(msg)
        self.name = t.name
        self.data["title"] = t.title
        self.data["description"] = t.description

    def save_costs(self, t):
        self.data["point_cost"] = str(t.point_cost)

    def save_dependents(self, t):
        self.data["depnames"] = self._pack_list([dep.name for dep in t.dependents])

    def save_assignee_and_collab(self, t):
        self.data["assignee"] = t.assignee
        self.data["collaborators"] = self._pack_list(t.collaborators)

    def save_priority_and_state(self, t):
        self.data["state"] = str(int(t.state))
        self.data["priority"] = str(float(t.priority))

    def save_tier(self, t):
        self.data["tier"] = str(int(t.tier))

    def save_tags(self, t):
        self.data["tags"] = self._pack_list(t.tags)

    def save_work_span(self, t):
        if t.work_span and t.work_span[0] is not None:
            self.data["work_start"] = t.work_span[0].isoformat()
        if t.work_span and t.work_span[1] is not None:
            self.data["work_end"] = t.work_span[1].isoformat()

    def save_uri_and_plugin(self, t):
        self.data["loading_plugin"] = t.loading_plugin
        self.data["uri"] = t.uri

    def save(self):
        with self._manipulate_existing_config(self.CONFIG_FILENAME) as config:
            if self.name not in config:
                config[self.name] = dict()
            config[self.name].update(self.data)

    @classmethod
    def get_all_target_names(cls):
        config = cls._load_existing_config(cls.CONFIG_FILENAME)
        return set(config.sections())

    @classmethod
    def get_loaded_targets_by_id(cls):
        ret = dict()
        for name in cls.get_all_target_names():
            ret[name] = data.BaseTarget.load_metadata(name, cls)
        return ret

    @classmethod
    def load_all_targets(cls):
        config = cls._load_existing_config(cls.CONFIG_FILENAME)
        ret = []
        for name in config.sections():
            ret.append(data.BaseTarget.load_metadata(name, cls))
        return ret

    @classmethod
    def bulk_save_metadata(cls, targets: typing.Iterable[data.BaseTarget]):
        saver = cls()
        for t in targets:
            t._pass_data_to_saver(saver)
        saver.save()


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
