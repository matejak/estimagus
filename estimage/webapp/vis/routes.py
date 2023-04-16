import io
import datetime
import collections

import flask
import flask_login

from . import bp
from .. import web_utils
from ... import utilities
from ... import simpledata as webdata
from ... import history
from ...visualize import utils, velocity, burndown, pert

import matplotlib
matplotlib.use('Agg')


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
    plt.close(figure)
    bytesio.seek(0)

    return flask.send_file(bytesio, download_name=filename, mimetype="image/svg+xml")


def get_pert_in_figure(estimation, task_name):
    fig = pert.get_pert_in_figure(estimation, task_name)
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)

    return fig


@bp.route('/<epic_name>-velocity.svg')
@flask_login.login_required
def visualize_velocity(epic_name):
    all_targets = webdata.RetroTarget.get_loaded_targets_by_id()
    all_events = webdata.EventManager.load()

    start = flask.current_app.config["PERIOD"]["start"]
    end = flask.current_app.config["PERIOD"]["end"]

    if epic_name == ".":
        targets_by_tiers = collections.defaultdict(list)
        for t in all_targets.values():
            targets_by_tiers[t.tier].append(t)

        aggregation = []
        for tier in range(max(targets_by_tiers.keys()) + 1):
            target_tree = utilities.reduce_subsets_from_sets(targets_by_tiers[tier])
            a = history.Aggregation.from_targets(target_tree, start, end)
            a.process_event_manager(all_events)
            aggregation.append(a)
    else:
        epic = all_targets[epic_name]
        aggregation = history.Aggregation.from_target(epic, start, end)
        aggregation.process_event_manager(all_events)

    cutoff_date = min(datetime.datetime.today(), end)

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
    model = web_utils.get_user_model(user_id, webdata.ProjTarget)
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

    fig = get_pert_in_figure(estimation, task_name)

    return send_figure_as_svg(fig, task_name)


@bp.route('/<epic_name>-burndown-<size>.svg')
@flask_login.login_required
def visualize_epic_burndown(epic_name, size):
    allowed_sizes = ("small", "normal")
    if size not in allowed_sizes:
        msg = "Figure size must be one of {allowed_sizes}, got '{size}' instead."
        raise ValueError(msg)

    all_targets = webdata.RetroTarget.get_loaded_targets_by_id()
    epic = all_targets[epic_name]

    return output_burndown([epic], size)


@bp.route('/tier<tier>-burndown-<size>.svg')
def visualize_overall_burndown(tier, size):
    allowed_sizes = ("small", "normal")
    if size not in allowed_sizes:
        msg = "Figure size must be one of {allowed_sizes}, got '{size}' instead."
        raise ValueError(msg)
    if (tier := int(tier)) < 0:
        msg = "Tier must be a positive number, got {tier}"
        raise ValueError(msg)

    all_targets = webdata.RetroTarget.get_loaded_targets_by_id()
    all_targets = {name: target for name, target in all_targets.items() if target.tier <= tier}
    target_tree = utilities.reduce_subsets_from_sets(list(all_targets.values()))

    return output_burndown(target_tree, size)


def output_burndown(target_tree, size):
    start = flask.current_app.config["PERIOD"]["start"]
    end = flask.current_app.config["PERIOD"]["end"]
    all_events = webdata.EventManager.load()

    aggregation = history.Aggregation.from_targets(target_tree, start, end)
    aggregation.process_event_manager(all_events)

    if size == "small":
        fig = burndown.MPLPointPlot(aggregation).get_small_figure()
        fig.set_size_inches(* SMALL_FIGURE_SIZE)
    else:
        fig = burndown.MPLPointPlot(aggregation).get_figure()
        fig.set_size_inches(* NORMAL_FIGURE_SIZE)

    basename = flask.request.path.split("/")[-1]

    return send_figure_as_svg(fig, basename)
