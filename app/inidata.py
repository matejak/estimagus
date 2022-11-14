import configparser
import contextlib

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


class IniTarget(data.BaseTarget, IniStorage):
    def save_metadata(self):
        for dep in self.dependents:
            dep.save_metadata()
        if not self.name:
            msg = "Coudln't save target, because its name is blank."
            raise RuntimeError(msg)
        with self._manipulate_existing_config() as config:
            config[self.name] = dict(
                title=self.title,
                description=self.description,
                depnames=",".join([dep.name for dep in self.dependents]),
            )

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
        for n in config[name].get("depnames", "").split(","):
            if not n:
                continue
            new = cls.load_metadata(n)
            ret.dependents.append(new)
        return ret

    def _save_point_cost(self, cost_str):
        with self._manipulate_existing_config() as config:
            config[self.name] = dict(
                point_cost=cost_str,
            )

    def _load_point_cost(self):
        config = self._load_existing_config()
        return config[self.name].get("point_cost", fallback=0)

    def _save_time_cost(self, cost_str):
        with self._manipulate_existing_config() as config:
            config[self.name] = dict(
                time_cost=cost_str,
            )

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
