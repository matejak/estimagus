import typing
import pathlib
import datetime
import dateutil.relativedelta
import dataclasses

import flask

from . import data
from . import inidata
from .persistence import entrydef, pollster, event


class IniInDirMixin:
    @classmethod
    @property
    def CONFIG_FILENAME(cls):
        try:
            datadir = pathlib.Path(flask.current_app.config["DATA_DIR"])
        except RuntimeError:
            datadir = pathlib.Path(".")
        ret = datadir / cls.CONFIG_BASENAME
        return ret


class RetroTargetIO(IniInDirMixin, entrydef.ini.IniTargetIO):
    CONFIG_BASENAME = "retrospective.ini"
    WHAT_IS_THIS = "retrospective target"


class ProjTargetIO(IniInDirMixin, entrydef.ini.IniTargetIO):
    CONFIG_BASENAME = "projective.ini"
    WHAT_IS_THIS = "projective target"


class UserPollsterBase(data.Pollster):
    def __init__(self, username, * args, ** kwargs):
        class pollster_io_class(IniInDirMixin, pollster.ini.IniPollsterIO):
            CONFIG_BASENAME = self.CONFIG_BASENAME
            WHAT_IS_THIS = "user pollster"

        super().__init__(* args, io_cls=pollster_io_class, ** kwargs)
        self.username = username
        self.set_namespace(f"user-{username}-")


class UserPollster(UserPollsterBase):
    CONFIG_BASENAME = "pollsters.ini"


class AuthoritativePollsterBase(data.Pollster):
    def __init__(self, * args, ** kwargs):
        class pollster_io_class(IniInDirMixin, pollster.ini.IniPollsterIO):
            CONFIG_BASENAME = self.CONFIG_BASENAME
            WHAT_IS_THIS = "authoritative pollster"

        super().__init__(* args, io_cls=pollster_io_class, ** kwargs)
        self.set_namespace("***-")


class AuthoritativePollster(AuthoritativePollsterBase):
    CONFIG_BASENAME = "pollsters.ini"


@dataclasses.dataclass
class Context:
    task_name: str
    own_estimation_exists: bool = False
    global_estimation_exists: bool = False

    def __init__(self, of_task):
        self.task_name = of_task
        self._own_estimate = None
        self._global_estimate = None

    def process_own_pollster(self, pollster: data.Pollster):
        self.own_estimation_exists = False
        self._own_estimate = None
        if pollster.knows_points(self.task_name):
            points = pollster.ask_points(self.task_name)
            self._own_estimate = data.Estimate.from_input(points)
            self.own_estimation_exists = True

    def process_global_pollster(self, pollster: data.Pollster):
        self.global_estimation_exists = False
        self._global_estimate = None
        if pollster.knows_points(self.task_name):
            self.global_estimation_exists = False
            points = pollster.ask_points(self.task_name)
            self._global_estimate = data.Estimate.from_input(points)
            self.global_estimation_exists = True

    @property
    def estimation(self) -> data.Estimate:
        if self.estimation_source == "none":
            msg = "No estimation exists"
            raise ValueError(msg)
        elif self.estimation_source == "own":
            return self.own_estimation
        elif self.estimation_source == "global":
            return self.global_estimation

    @property
    def own_estimation(self) -> data.Estimate:
        if not self.own_estimation_exists:
            msg = "Own estimation doesn't exist"
            raise ValueError(msg)
        return self._own_estimate

    @property
    def global_estimation(self) -> data.Estimate:
        if not self.global_estimation_exists:
            msg = "Global estimation doesn't exist"
            raise ValueError(msg)
        return self._global_estimate

    @property
    def estimate_status(self) -> str:
        ret = "absent"
        if self.own_estimation_exists != self.global_estimation_exists:
            ret = "single"
        elif self.own_estimation_exists and self.global_estimation_exists:
            ret = self._get_status_of_existing_estimation()
        return ret

    def _get_status_of_existing_estimation(self):
        if self._own_estimate == self._global_estimate:
            ret = "duplicate"
        else:
            ret = "contradictory"
        return ret

    @property
    def estimation_source(self) -> str:
        ret = "none"
        if self.global_estimation_exists:
            ret = "global"
        if self.own_estimation_exists:
            ret = "own"
        return ret


class EventManager(data.EventManager):
    CONFIG_BASENAME = "events.ini"

    def __init__(self, * args, ** kwargs):
        class eventmgr_io_class(IniInDirMixin, event.ini.IniEventsIO):
            CONFIG_BASENAME = self.CONFIG_BASENAME
            WHAT_IS_THIS = "events manager"

        super().__init__(* args, io_cls=eventmgr_io_class, ** kwargs)


class AppData(inidata.IniAppdata):
    CONFIG_BASENAME = "appdata.ini"

    def _get_default_retrospective_period(self):
        today = datetime.datetime.today()
        today_first_of_month = datetime.datetime(today.year, today.month, 1)
        beginning = today_first_of_month - dateutil.relativedelta.relativedelta(months=1)
        end = today_first_of_month + dateutil.relativedelta.relativedelta(months=2, days=-1)
        return (beginning, end)

    def _get_default_projective_quarter(self):
        return ""

    def _get_default_retrospective_quarter(self):
        return ""


def get_model(targets_tree_without_duplicates, cls=None):
    model = data.EstiModel()
    if not targets_tree_without_duplicates:
        return model
    if cls is None:
        cls = targets_tree_without_duplicates[0].__class__
    main_composition = cls.to_tree(targets_tree_without_duplicates)
    model.use_composition(main_composition)
    return model


def _create_distance_task_tuples(
        relevant_tasks, reference_estimate,
        distance_threshold: float, rank_threshold: float):
    distance_task_tuples = list()
    for t in relevant_tasks:
        distance = abs(t.nominal_point_estimate.expected - reference_estimate.expected)
        rank = t.nominal_point_estimate.rank_distance(reference_estimate)
        if (distance <= distance_threshold or rank <= rank_threshold):
            distance_task_tuples.append((distance, t))
    return distance_task_tuples


def order_nearby_tasks(
        reference_task: data.TaskModel, all_tasks: typing.Iterable[data.TaskModel],
        distance_threshold: float, rank_threshold: float) -> typing.List[data.TaskModel]:
    reference_estimate = reference_task.nominal_point_estimate
    relevant_tasks = [t for t in all_tasks if t.name != reference_task.name]
    distance_task_tuples = _create_distance_task_tuples(
        relevant_tasks, reference_estimate, distance_threshold, rank_threshold)
    sorted_distance_tasks = sorted(distance_task_tuples, key=lambda x: x[0])
    return [dt[1] for dt in sorted_distance_tasks]
