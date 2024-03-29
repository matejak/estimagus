import io
import datetime

import flask
import flask_login
import markupsafe

import numpy as np
import scipy as sp
import matplotlib

from . import bp
from .. import web_utils
from ... import history, utilities
from ...statops import func
from ... import simpledata as webdata
from ...visualize import utils, velocity, burndown, pert, completion


WIDE_FIGURE_SIZE = (12.0, 4.4)
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
    pert_class = flask.current_app.get_final_class("PertPlotter")
    fig = pert.get_pert_in_figure(estimation, task_name, pert_class)
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)

    return fig


def get_aggregation(cards_tree_without_duplicates):

    all_events = webdata.EventManager()
    all_events.load()
    statuses = flask.current_app.get_final_class("Statuses")()
    start, end = flask.current_app.get_config_option("RETROSPECTIVE_PERIOD")
    aggregation = history.Aggregation.from_cards(cards_tree_without_duplicates, start, end, statuses)
    aggregation.process_event_manager(all_events)

    return aggregation


@bp.route('/completion.svg')
@flask_login.login_required
def visualize_completion():
    user = flask_login.current_user
    user_id = user.get_id()

    all_cards_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    all_cards = list(all_cards_by_id.values())
    cards_tree_without_duplicates = utilities.reduce_subsets_from_sets([t for t in all_cards if t.tier == 0])

    aggregation = get_aggregation(cards_tree_without_duplicates)

    model = web_utils.get_user_model(user_id, cards_tree_without_duplicates)

    # TODO: There may be inconsistencies when the data are newer than when the cutoff ends
    todo = model.remaining_point_estimate.expected
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
    return send_figure_as_svg(fig, "completion.svg")


@bp.route('/velocity-fit.svg')
@flask_login.login_required
def visualize_velocity_fit():
    user = flask_login.current_user
    user_id = user.get_id()
    all_events = webdata.EventManager()
    all_events.load()

    all_cards_by_id, _ = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    all_cards = list(all_cards_by_id.values())
    cards_tree_without_duplicates = utilities.reduce_subsets_from_sets([t for t in all_cards if t.tier == 0])

    statuses = flask.current_app.get_final_class("Statuses")()
    start, end = flask.current_app.get_config_option("RETROSPECTIVE_PERIOD")
    aggregation = history.Aggregation.from_cards(cards_tree_without_duplicates, start, end, statuses)
    aggregation.process_event_manager(all_events)

    velocity_array = aggregation.get_velocity_array()
    nonzero_weekly_velocity = func.get_nonzero_velocity(velocity_array) * 7

    matplotlib.use("svg")

    fit_class = flask.current_app.get_final_class("VelocityFitPlot")

    fig = fit_class(nonzero_weekly_velocity).get_figure()
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)
    return send_figure_as_svg(fig, "completion.svg")


@bp.route('/<epic_name>-velocity.svg')
@flask_login.login_required
def visualize_velocity(epic_name):
    cls, loader = web_utils.get_retro_loader()
    all_cards = loader.get_loaded_cards_by_id(cls)

    user = flask_login.current_user
    user_id = user.get_id()
    all_events = webdata.EventManager()
    all_events.load()

    statuses = flask.current_app.get_final_class("Statuses")()
    start, end = flask.current_app.get_config_option("RETROSPECTIVE_PERIOD")
    velocity_class = flask.current_app.get_final_class("MPLVelocityPlot")

    if epic_name == ".":
        card_tree = utilities.reduce_subsets_from_sets(list(all_cards.values()))
        model = web_utils.get_user_model(user_id, card_tree)
        model.update_cards_with_values(card_tree)

        aggregation = history.Aggregation.from_cards(card_tree, start, end, statuses)
    else:
        epic = all_cards[epic_name]
        model = web_utils.get_user_model(user_id, [epic])
        model.update_cards_with_values([epic])

        aggregation = history.Aggregation.from_card(epic, start, end, statuses)

    aggregation.process_event_manager(all_events)
    cutoff_date = min(datetime.datetime.today(), end)

    matplotlib.use("svg")
    fig = velocity_class(aggregation).get_figure(cutoff_date)
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)
    return send_figure_as_svg(fig, epic_name)


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

    user = flask_login.current_user
    user_id = user.get_id()

    tasks, model = web_utils.get_all_tasks_by_id_and_user_model("proj", user_id)

    if nominal_or_remaining == "nominal":
        estimation = model.nominal_point_estimate
    else:
        estimation = model.remaining_point_estimate

    matplotlib.use("svg")
    fig = get_pert_in_figure(estimation, "all")

    return send_figure_as_svg(fig, "all")


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

    return send_figure_as_svg(fig, task_name)


@bp.route('/<epic_name>-burndown-<size>.svg')
@flask_login.login_required
def visualize_epic_burndown(epic_name, size):
    allowed_sizes = ("small", "normal")
    if size not in allowed_sizes:
        msg = f"Figure size must be one of {allowed_sizes}, got '{size}' instead."
        raise ValueError(msg)

    cls, loader = web_utils.get_retro_loader()
    all_cards = loader.get_loaded_cards_by_id(cls)
    epic = all_cards[epic_name]

    user = flask_login.current_user
    user_id = user.get_id()
    model = web_utils.get_user_model(user_id, [epic])
    model.update_cards_with_values([epic])

    return output_burndown([epic], size)


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

    cls, loader = web_utils.get_retro_loader()
    all_cards = loader.get_loaded_cards_by_id(cls)
    all_cards = [card for name, card in all_cards.items() if card.tier <= tier]
    card_tree = utilities.reduce_subsets_from_sets(all_cards)

    user = flask_login.current_user
    user_id = user.get_id()
    model = web_utils.get_user_model(user_id, card_tree)
    model.update_cards_with_values(card_tree)

    return output_burndown(card_tree, size)


def output_burndown(card_tree, size):
    start, end = flask.current_app.get_config_option("RETROSPECTIVE_PERIOD")
    all_events = webdata.EventManager()
    all_events.load()

    statuses = flask.current_app.get_final_class("Statuses")()
    aggregation = history.Aggregation.from_cards(card_tree, start, end, statuses)
    aggregation.process_event_manager(all_events)

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

    return send_figure_as_svg(fig, basename)
