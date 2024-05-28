import io
import datetime
import collections

import flask
import flask_login
import markupsafe

import numpy as np
import matplotlib

from . import bp
from .. import web_utils, routers
from ... import history, utilities
from ...statops import func
from ... import simpledata as webdata
from ...visualize import utils, pert
# need to import those to ensure that they are discovered by the app
from ...visualize import velocity, completion


WIDE_FIGURE_SIZE = (12.0, 4.4)
NORMAL_FIGURE_SIZE = (6.0, 4.4)
SMALL_FIGURE_SIZE = (2.2, 1.6)


ImageOutput = collections.namedtuple(
        "ImageOutput",
        ("extension", "format", "mimetype", "savefig_kwargs"))
OUTPUT_TYPES = dict(
    svg=ImageOutput(
        extension="svg", format="svg", mimetype="image/svg+xml",
        savefig_kwargs=dict(pad_inches=0, dpi="figure")),
    png=ImageOutput(
        extension="png", format="png", mimetype="image/png",
        savefig_kwargs=dict()),
)


def send_figure_as(figure, basename, output_string):
    output_type = OUTPUT_TYPES[output_string]

    plt = utils.get_standard_pyplot()
    filename = f"{basename}.{output_type.extension}"

    bytesio = io.BytesIO()
    figure.savefig(bytesio, format=output_type.format, bbox_inches='tight', ** output_type.savefig_kwargs)
    figure.clear()
    plt.close(figure)
    bytesio.seek(0)

    return flask.send_file(bytesio, download_name=filename, mimetype="image/svg+xml")


def get_pert_in_figure(estimation, task_name):
    pert_class = flask.current_app.get_final_class("PertPlotter")
    fig = pert.get_pert_in_figure(estimation, task_name, pert_class)
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)

    return fig


@bp.route('/completion.svg')
@flask_login.login_required
def visualize_completion():
    router = routers.AggregationRouter(mode="retro")
    tier0_cards = [c for c in router.cards_tree_without_duplicates if c.tier == 0]
    aggregation = router.get_aggregation_of_cards(tier0_cards)

    # TODO: There may be inconsistencies when the data are newer than when the cutoff ends
    todo = router.model.remaining_point_estimate.expected
    summary = history.aggregation.Summary(aggregation, min(aggregation.end, datetime.datetime.today()))
    todo = summary.cutoff_todo + summary.cutoff_underway

    velocity_array = aggregation.get_velocity_array()
    nonzero_daily_velocity = func.get_nonzero_velocity(velocity_array)

    mu, sigma = func.autoestimate_lognorm(nonzero_daily_velocity)
    v_mean, v_std = func.get_lognorm_mean_stdev(mu, sigma)

    time_dom = np.linspace(
        func.get_time_to_completion(v_mean, v_std, todo, 0.001),
        func.get_time_to_completion(v_mean, v_std, todo, 0.99) + 1,
        80)
    completion_cdf = func.get_prob_of_completion_vector(v_mean, v_std, todo, time_dom)

    ppf = lambda x: func.get_time_to_completion(v_mean, v_std, todo, x)

    time_dom = np.concatenate(([0, max(0, time_dom[0] - 1)], time_dom))
    completion_cdf = np.concatenate(([0, 0], completion_cdf))

    matplotlib.use("svg")

    completion_class = flask.current_app.get_final_class("MPLCompletionPlot")

    fig = completion_class(
        (aggregation.start, aggregation.end), time_dom, completion_cdf, ppf).get_figure()
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)
    return send_figure_as(fig, "completion", "svg")


@bp.route('/velocity-fit.svg')
@flask_login.login_required
def visualize_velocity_fit():
    router = routers.AggregationRouter(mode="retro")
    aggregation = router.aggregation

    velocity_array = aggregation.get_velocity_array()
    nonzero_weekly_velocity = func.get_nonzero_velocity(velocity_array) * 7

    matplotlib.use("svg")

    fit_class = flask.current_app.get_final_class("VelocityFitPlot")

    fig = fit_class(nonzero_weekly_velocity).get_figure()
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)
    return send_figure_as(fig, "completion", "svg")


@bp.route('/<epic_name>-velocity.svg')
@flask_login.login_required
def visualize_velocity_of_epic(epic_name):
    velocity_class = flask.current_app.get_final_class("MPLVelocityPlot")

    r = routers.AggregationRouter(mode="retro")
    aggregation = r.get_aggregation_of_names([epic_name])

    cutoff_date = min(datetime.datetime.today(), aggregation.end)

    matplotlib.use("svg")
    fig = velocity_class(aggregation).get_figure(cutoff_date)
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)
    return send_figure_as(fig, epic_name, "svg")


@bp.route('/velocity-complete.svg')
@flask_login.login_required
def visualize_complete_velocity():
    velocity_class = flask.current_app.get_final_class("MPLVelocityPlot")

    r = routers.AggregationRouter(mode="retro")
    aggregation = r.aggregation

    cutoff_date = min(datetime.datetime.today(), aggregation.end)

    matplotlib.use("svg")
    fig = velocity_class(aggregation).get_figure(cutoff_date)
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)
    return send_figure_as(fig, "all", "svg")


@bp.route('/all_tasks-<nominal_or_remaining>-pert.svg')
@flask_login.login_required
def visualize_all_projective_tasks(nominal_or_remaining):
    allowed_modes = ("nominal", "remaining")
    if nominal_or_remaining not in allowed_modes:
        msg = (
            f"Attempt to visualize all tasks "
            "and not setting mode to one of {allowed_modes}, "
            f"but to '{nominal_or_remaining}'."
        )
        flask.flash(msg)
        raise ValueError(msg)

    r = routers.ModelRouter(mode="proj")

    if nominal_or_remaining == "nominal":
        estimation = r.model.nominal_point_estimate
    else:
        estimation = r.model.remaining_point_estimate

    matplotlib.use("svg")
    fig = get_pert_in_figure(estimation, "all")

    return send_figure_as(fig, "all", "svg")


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

    if nominal_or_remaining == "nominal":
        estimation = model.nominal_point_estimate_of(task_name)
    else:
        estimation = model.remaining_point_estimate_of(task_name)

    matplotlib.use("svg")
    fig = get_pert_in_figure(estimation, task_name)

    return send_figure_as(fig, task_name, "svg")


@bp.route('/<epic_name>-burndown-<size>.svg')
@flask_login.login_required
def visualize_epic_burndown(epic_name, size):
    allowed_sizes = ("small", "normal")
    if size not in allowed_sizes:
        msg = f"Figure size must be one of {allowed_sizes}, got '{size}' instead."
        raise ValueError(msg)

    r = routers.AggregationRouter(mode="retro")
    a = r.get_aggregation_of_names([epic_name])

    return output_burndown(a, size)


@bp.route('/tier<tier>-burndown-<size>.svg')
@flask_login.login_required
def visualize_overall_burndown(tier, size):
    allowed_sizes = ("small", "normal", "wide")
    if size not in allowed_sizes:
        msg = f"Figure size must be one of {allowed_sizes}, got '{size}' instead."
        raise ValueError(msg)
    if (tier := int(tier)) < 0:
        msg = "Tier must be a non-negative number, got {tier}"
        raise ValueError(msg)

    r = routers.AggregationRouter(mode="retro")
    right_tier_cards = [c for c in r.cards_tree_without_duplicates if c.tier <= 0]
    aggregation = r.get_aggregation_of_cards(right_tier_cards)

    return output_burndown(aggregation, size)


def output_burndown(aggregation, size):
    burndown_class = flask.current_app.get_final_class("MPLPointPlot")

    matplotlib.use("svg")
    if size == "small":
        fig = burndown_class(aggregation).get_small_figure()
        fig.set_size_inches(* SMALL_FIGURE_SIZE)
    elif size == "wide":
        fig = burndown_class(aggregation).get_figure()
        fig.set_size_inches(* WIDE_FIGURE_SIZE)
    else:
        fig = burndown_class(aggregation).get_figure()
        fig.set_size_inches(* NORMAL_FIGURE_SIZE)

    basename = flask.request.path.split("/")[-1]

    return send_figure_as(fig, basename, "svg")
