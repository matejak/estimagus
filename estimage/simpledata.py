import typing

from . import data
from . import inidata


class Target(inidata.IniTarget):
    CONFIG_FILENAME = "targets.ini"


class UserPollsterBase(data.Pollster):
    def __init__(self, username, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.username = username
        self.set_namespace(f"user-{username}-")


class UserPollster(UserPollsterBase, inidata.IniPollster):
    CONFIG_FILENAME = "pollsters.ini"


class AuthoritativePollsterBase(data.Pollster):
    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.set_namespace("***-")


class AuthoritativePollster(AuthoritativePollsterBase, inidata.IniPollster):
    CONFIG_FILENAME = "pollsters.ini"


class Pollster(inidata.IniPollster):
    CONFIG_FILENAME = "pollsters.ini"

    def __init__(self, poll_id_prefix, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.set_namespace(poll_id_prefix)

    def _keyname(self, ns, name):
        keyname = f"{ns}{name}"
        return keyname


class EventManager(inidata.IniEvents):
    CONFIG_FILENAME = "events.ini"


def get_model(targets_tree_without_duplicates):
    main_composition = Target.to_tree(targets_tree_without_duplicates)
    model = data.EstiModel()
    model.use_composition(main_composition)
    return model


def order_nearby_tasks(
        reference_task: data.TaskModel, all_tasks: typing.Iterable[data.TaskModel],
        distance_threshold: float, rank_threshold: float) -> typing.List[data.TaskModel]:
    reference_estimate = reference_task.point_estimate
    expected = reference_estimate.expected

    distance_task_tuples = list()
    for t in all_tasks:
        if t.name == reference_task.name:
            continue
        distance = abs(t.point_estimate.expected - expected)
        rank = t.point_estimate.rank_distance(reference_estimate)
        if (distance <= distance_threshold or rank <= rank_threshold):
            distance_task_tuples.append((distance, t))
    sorted_distance_tasks = sorted(distance_task_tuples, key=lambda x: x[0])
    return [dt[1] for dt in sorted_distance_tasks]
