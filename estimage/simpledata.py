import typing
import pathlib

import flask

from . import data
from . import inidata


class IniInDirMixin:
    @classmethod
    @property
    def CONFIG_FILENAME(cls):
        try:
            datadir = pathlib.Path(flask.current_app.config["DATA_DIR"])
        except RuntimeError:
            datadir = pathlib.Path(".")
        return datadir / cls.CONFIG_BASENAME


class RetroTarget(IniInDirMixin, inidata.IniTarget):
    CONFIG_BASENAME = "retrospective.ini"


class ProjTarget(IniInDirMixin, inidata.IniTarget):
    CONFIG_BASENAME = "projective.ini"


class UserPollsterBase(data.Pollster):
    def __init__(self, username, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.username = username
        self.set_namespace(f"user-{username}-")


class UserPollster(IniInDirMixin, UserPollsterBase, inidata.IniPollster):
    CONFIG_BASENAME = "pollsters.ini"


class AuthoritativePollsterBase(data.Pollster):
    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.set_namespace("***-")


class AuthoritativePollster(IniInDirMixin, AuthoritativePollsterBase, inidata.IniPollster):
    CONFIG_BASENAME = "pollsters.ini"


class Pollster(inidata.IniPollster):
    CONFIG_BASENAME = "pollsters.ini"

    def __init__(self, poll_id_prefix, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.set_namespace(poll_id_prefix)

    def _keyname(self, ns, name):
        keyname = f"{ns}{name}"
        return keyname


class EventManager(IniInDirMixin, inidata.IniEvents):
    CONFIG_BASENAME = "events.ini"


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
