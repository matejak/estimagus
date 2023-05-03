import configparser
import dataclasses
import contextlib
import typing
import datetime
import pathlib

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

    @classmethod
    @contextlib.contextmanager
    def _manipulate_existing_config(cls):
        config = cls._load_existing_config()
        try:
            yield config
        finally:
            with open(cls.CONFIG_FILENAME, "w") as f:
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
        with self._manipulate_existing_config() as config:
            self._save_metadata(config)

    def _save_metadata(self, config):
        for dep in self.dependents:
            dep._save_metadata(config)
        if not self.name:
            msg = "Coudln't save target, because its name is blank."
            raise RuntimeError(msg)
        metadata = dict(
            title=self.title,
            description=self.description,
            depnames=",".join([dep.name for dep in self.dependents]),
            state=str(int(self.state)),
            collaborators=",".join(self.collaborators),
            assignee=self.assignee,
            priority=str(float(self.priority)),
            status_summary=self.status_summary,
            tags=",".join(self.tags),
            tier=str(self.tier),
            uri=self.uri,
            point_cost=str(self.point_cost),
            loading_plugin=self.loading_plugin,
        )
        if self.work_span and self.work_span[0] is not None:
            metadata["work_start"] = self.work_span[0].isoformat()
        if self.work_span and self.work_span[1] is not None:
            metadata["work_end"] = self.work_span[1].isoformat()
        if self.status_summary_time:
            metadata["status_summary_time"] = self.status_summary_time.isoformat()
        if self.name not in config:
            config[self.name] = dict()
        config[self.name].update(metadata)

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
    def bulk_save_metadata(cls, targets: typing.Iterable[data.BaseTarget]):
        with cls._manipulate_existing_config() as config:
            for t in targets:
                t._save_metadata(config)

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
        our_config = config[name]
        ret.title = our_config.get("title", "")
        ret.description = our_config.get("description", "")
        state = our_config.get("state", data.State.unknown)
        ret.state = data.State(int(state))

        ret.point_cost = float(our_config.get("point_cost", 0))

        ret.priority = float(our_config.get("priority", ret.priority))
        ret.status_summary = our_config.get("status_summary", "")
        ret.collaborators = our_config.get("collaborators", "").split(",")
        ret.assignee = our_config.get("assignee", "")
        ret.tags = set(our_config.get("tags", "").split(","))
        ret.tier = int(our_config.get("tier", "0"))
        ret.uri = our_config.get("uri", "")
        ret.loading_plugin = our_config.get("loading_plugin", "")

        span = [None, None]
        if "work_start" in our_config:
            span[0] = datetime.datetime.fromisoformat(our_config["work_start"])
        if "work_end" in our_config:
            span[1] = datetime.datetime.fromisoformat(our_config["work_end"])
        if span[0] or span[1]:
            ret.work_span = tuple(span)
        if "status_summary_time" in our_config:
            ret.status_summary_time = datetime.datetime.fromisoformat(our_config["status_summary_time"])

        for n in our_config.get("depnames", "").split(","):
            if not n:
                continue
            new = cls._load_metadata(n, config)
            ret.dependents.append(new)
        return ret


class IniPollster(data.Pollster, IniStorage):
    def _keyname(self, ns, name):
        keyname = f"{ns}-{name}"
        return keyname

    def _ask_points(self, ns, name, config=None):
        keyname = self._keyname(ns, name)

        if not config:
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

    def provide_info_about(self, names: typing.Iterable[str], config=None) -> typing.Dict[str, data.Estimate]:
        if not config:
            config = self._load_existing_config()
        ret = dict()
        for name in names:
            if self._knows_points(self._namespace, name, config=config):
                ret[name] = self._ask_points(self._namespace, name, config)
        return ret


class IniEvents(data.EventManager, IniStorage):
    def save(self):
        task_names = self.get_referenced_task_names()
        with self._manipulate_existing_config() as config:
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

        with self._manipulate_existing_config() as config:
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
        config = result._load_existing_config()
        result._load_retrospective_period(config)
        result._load_quarters(config)
        return result
