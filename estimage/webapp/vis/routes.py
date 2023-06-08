import io
import datetime

import flask
import flask_login
import markupsafe

import numpy as np
import matplotlib

from . import bp
from .. import web_utils
from ... import utilities
from ... import simpledata as webdata
from ... import history
from ...visualize import utils, velocity, burndown, pert, completion


NORMAL_FIGURE_SIZE = (6.0, 4.4)
SMALL_FIGURE_SIZE = (2.2, 1.6)


def send_figure_as_png(figure, basename):
    plt = utils.get_standard_pyplot()
    filename = basename + ".png"

    bytesio = io.BytesIO()
    figure.savefig(bytesio, format="png", bbox_inches='tight')
    plt.close(figure)
    bytesio.seek(0)

    return flask.send_file(bytesio, download_name=filename, mimetype="image/png")


def send_figure_as_svg(figure, basename):
    plt = utils.get_standard_pyplot()
    filename = basename + ".svg"

    bytesio = io.BytesIO()
    figure.savefig(bytesio, pad_inches=0, dpi="figure", format="svg", bbox_inches='tight')
    figure.clear()
    plt.close(figure)
    bytesio.seek(0)

    return flask.send_file(bytesio, download_name=filename, mimetype="image/svg+xml")


def get_pert_in_figure(estimation, task_name):
    pert_class = flask.current_app.config["classes"]["PertPlotter"]
    fig = pert.get_pert_in_figure(estimation, task_name, pert_class)
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)

    return fig


@bp.route('/completion.svg')
@flask_login.login_required
def visualize_completion():
    user = flask_login.current_user
    user_id = user.get_id()
    all_events = webdata.EventManager()
    all_events.load()

    all_targets_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    all_targets = list(all_targets_by_id.values())
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets([t for t in all_targets if t.tier == 0])
    model = web_utils.get_user_model(user_id, targets_tree_without_duplicates)
    todo = model.remaining_point_estimate

    start, end = flask.current_app.config["RETROSPECTIVE_PERIOD"]
    aggregation = history.Aggregation.from_targets(targets_tree_without_duplicates, start, end)
    aggregation.process_event_manager(all_events)

    velocity_array = aggregation.get_velocity_array()
    velocity_array = velocity_array[velocity_array > 0] * 7
    velocity_mean = velocity_array.mean()
    velocity_array = np.convolve(velocity_array, np.ones(7) / 7, "same")
    velocity_stdev = velocity_array.var()**0.5

    matplotlib.use("svg")
    print(f"{velocity_mean=}, {velocity_stdev=}")
    print(f"{velocity_array=}")
    fig = completion.MPLCompletionPlot(todo, (velocity_mean, velocity_stdev)).get_figure()
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)
    return send_figure_as_svg(fig, "completion.svg")


@bp.route('/<epic_name>-velocity.svg')
@flask_login.login_required
def visualize_velocity(epic_name):
    cls, loader = web_utils.get_retro_loader()
    all_targets = loader.get_loaded_targets_by_id(cls)

    user = flask_login.current_user
    user_id = user.get_id()
    all_events = webdata.EventManager()
    all_events.load()

    start, end = flask.current_app.config["RETROSPECTIVE_PERIOD"]

    if epic_name == ".":
        target_tree = utilities.reduce_subsets_from_sets(list(all_targets.values()))
        model = web_utils.get_user_model(user_id, target_tree)
        model.update_targets_with_values(target_tree)

        aggregation = history.Aggregation.from_targets(target_tree, start, end)
    else:
        epic = all_targets[epic_name]
        model = web_utils.get_user_model(user_id, [epic])
        model.update_targets_with_values([epic])

        aggregation = history.Aggregation.from_target(epic, start, end)

    aggregation.process_event_manager(all_events)
    cutoff_date = min(datetime.datetime.today(), end)

    matplotlib.use("svg")
    fig = velocity.MPLVelocityPlot(aggregation).get_figure(cutoff_date)
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)
    return send_figure_as_svg(fig, epic_name)


@bp.route('/<task_name>-<nominal_or_remaining>-pert.svg')
@flask_login.login_required
def visualize_task(task_name, nominal_or_remaining):
    allowed_modes = ("nominal", "remaining")
    if nominal_or_remaining not in allowed_modes:
        msg = (
            f"Attempt to visualize {task_name} "
            "and not setting mode to one of {allowed_modes}, "
            f"but to '{nominal_or_remaining}'."
        )
        flask.flash(msg)
        raise ValueError(msg)

    user = flask_login.current_user
    user_id = user.get_id()

    tasks, model = web_utils.get_all_tasks_by_id_and_user_model("proj", user_id)
    if task_name not in tasks:
        tasks, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    if task_name not in tasks:
        return (f"Unable to find task '{markupsafe.escape(task_name)}'", 500)

    if task_name == ".":
        if nominal_or_remaining == "nominal":
            estimation = model.nominal_point_estimate
        else:
            estimation = model.remaining_point_estimate
    else:
        if nominal_or_remaining == "nominal":
            estimation = model.nominal_point_estimate_of(task_name)
        else:
            estimation = model.remaining_point_estimate_of(task_name)

    matplotlib.use("svg")
    fig = get_pert_in_figure(estimation, task_name)

    return send_figure_as_svg(fig, task_name)


@bp.route('/<epic_name>-burndown-<size>.svg')
@flask_login.login_required
def visualize_epic_burndown(epic_name, size):
    allowed_sizes = ("small", "normal")
    if size not in allowed_sizes:
        msg = "Figure size must be one of {allowed_sizes}, got '{size}' instead."
        raise ValueError(msg)

    cls, loader = web_utils.get_retro_loader()
    all_targets = loader.get_loaded_targets_by_id(cls)
    epic = all_targets[epic_name]

    user = flask_login.current_user
    user_id = user.get_id()
    model = web_utils.get_user_model(user_id, [epic])
    model.update_targets_with_values([epic])

    return output_burndown([epic], size)


@bp.route('/tier<tier>-burndown-<size>.svg')
@flask_login.login_required
def visualize_overall_burndown(tier, size):
    allowed_sizes = ("small", "normal")
    if size not in allowed_sizes:
        msg = "Figure size must be one of {allowed_sizes}, got '{size}' instead."
        raise ValueError(msg)
    if (tier := int(tier)) < 0:
        msg = "Tier must be a non-negative number, got {tier}"
        raise ValueError(msg)

    cls, loader = web_utils.get_retro_loader()
    all_targets = loader.get_loaded_targets_by_id(cls)
    all_targets = [target for name, target in all_targets.items() if target.tier <= tier]
    target_tree = utilities.reduce_subsets_from_sets(all_targets)

    user = flask_login.current_user
    user_id = user.get_id()
    model = web_utils.get_user_model(user_id, target_tree)
    model.update_targets_with_values(target_tree)

    return output_burndown(target_tree, size)


def output_burndown(target_tree, size):
    start, end = flask.current_app.config["RETROSPECTIVE_PERIOD"]
    all_events = webdata.EventManager()
    all_events.load()

    aggregation = history.Aggregation.from_targets(target_tree, start, end)
    aggregation.process_event_manager(all_events)

    matplotlib.use("svg")
    if size == "small":
        fig = burndown.MPLPointPlot(aggregation).get_small_figure()
        fig.set_size_inches(* SMALL_FIGURE_SIZE)
    else:
        fig = burndown.MPLPointPlot(aggregation).get_figure()
        fig.set_size_inches(* NORMAL_FIGURE_SIZE)

    basename = flask.request.path.split("/")[-1]

    return send_figure_as_svg(fig, basename)
