import io
import datetime

import flask
import flask_login

from . import bp
from .. import web_utils
from ... import utilities
from ... import simpledata as webdata
from ... import history

import matplotlib
matplotlib.use('Agg')


NORMAL_FIGURE_SIZE = (6.0, 4.4)
SMALL_FIGURE_SIZE = (2.2, 1.6)


def send_figure_as_png(figure, basename):
    plt = history.get_standard_pyplot()
    filename = basename + ".png"

    bytesio = io.BytesIO()
    figure.savefig(bytesio, format="png", bbox_inches='tight')
    plt.close(figure)
    bytesio.seek(0)

    return flask.send_file(bytesio, download_name=filename, mimetype="image/png")


def send_figure_as_svg(figure, basename):
    plt = history.get_standard_pyplot()
    filename = basename + ".svg"

    bytesio = io.BytesIO()
    figure.savefig(bytesio, pad_inches=0, dpi="figure", format="svg", bbox_inches='tight')
    plt.close(figure)
    bytesio.seek(0)

    return flask.send_file(bytesio, download_name=filename, mimetype="image/svg+xml")


def plot_continuous_pert(ax, pert, expected, task_name):
    ax.plot(pert[0], pert[1], 'b-', lw=2, label=f'task {task_name}')
    ax.axvline(expected, color="orange", label="expected value")


def plot_delta_pert(ax, pert, expected, task_name):
    dom = pert[0]
    ax.plot(dom, 0 * dom, 'b-', lw=2, label=f'task {task_name}')
    ax.axvline(expected, color="orange", label="expected value", zorder=2)
    # ax.arrow(expected, 0, 0, 1, fc='b', ec="b", lw=2, width=0.01, zorder=2)
    ax.set_ylim(-0.1, 1.1)
    ax.set_xlim(max(dom[0], -0.1), max(dom[-1], 0))
    ax.annotate(
        "", xy=(expected, 1), xycoords='data', xytext=(expected, 0), textcoords='data',
        arrowprops=dict(arrowstyle="->", connectionstyle="arc3", ec="b", lw=2), zorder=4)
    ax.scatter(expected, 0, ec="b", fc="w", lw=2, zorder=3)


def get_pert_in_figure(estimation, task_name):
    pert = estimation.get_pert()
    plt = history.get_standard_pyplot()

    fig, ax = plt.subplots(1, 1)
    if estimation.sigma == 0:
        plot_delta_pert(ax, pert, estimation.expected, task_name)
    else:
        plot_continuous_pert(ax, pert, estimation.expected, task_name)

    ax.set_xlabel("points")
    ax.set_ylabel("probability density")
    ax.set_yticklabels([])
    ax.grid()
    ax.legend()

    return fig


@bp.route('/<epic_name>-velocity.svg')
@flask_login.login_required
def visualize_velocity(epic_name):
    all_targets = webdata.RetroTarget.get_loaded_targets_by_id()
    target_tree = utilities.reduce_subsets_from_sets(list(all_targets.values()))
    all_events = webdata.EventManager.load()

    start = flask.current_app.config["PERIOD"]["start"]
    end = flask.current_app.config["PERIOD"]["end"]

    if epic_name == ".":
        aggregation = history.Aggregation.from_targets(target_tree, start, end)
    else:
        epic = all_targets[epic_name]
        aggregation = history.Aggregation.from_target(epic, start, end)

    aggregation.process_event_manager(all_events)
    cutoff_date = min(datetime.datetime.today(), end)

    fig = history.MPLVelocityPlot(aggregation).get_figure(cutoff_date)
    fig.set_size_inches(* NORMAL_FIGURE_SIZE)
    return send_figure_as_svg(fig, epic_name)


@bp.route('/<task_name>-pert.svg')
@flask_login.login_required
def visualize_task(task_name):
    user = flask_login.current_user

    user_id = user.get_id()
    model = web_utils.get_user_model(user_id, webdata.ProjTarget)
    if task_name == ".":
        estimation = model.nominal_point_estimate
    else:
        estimation = model.nominal_point_estimate_of(task_name)

    fig = get_pert_in_figure(estimation, task_name)

    return send_figure_as_svg(fig, task_name)


@bp.route('/<epic_name>-<size>-burndown.svg')
@flask_login.login_required
def visualize_burndown(epic_name, size):
    assert size in ("small", "normal")
    all_targets = webdata.RetroTarget.get_loaded_targets_by_id()
    target_tree = utilities.reduce_subsets_from_sets(list(all_targets.values()))
    all_events = webdata.EventManager.load()

    start = flask.current_app.config["PERIOD"]["start"]
    end = flask.current_app.config["PERIOD"]["end"]

    if epic_name == ".":
        aggregation = history.Aggregation.from_targets(target_tree, start, end)
    else:
        epic = all_targets[epic_name]
        aggregation = history.Aggregation.from_target(epic, start, end)

    aggregation.process_event_manager(all_events)

    if size == "small":
        fig = history.MPLPointPlot(aggregation).get_small_figure()
        fig.set_size_inches(* SMALL_FIGURE_SIZE)
    else:
        fig = history.MPLPointPlot(aggregation).get_figure()
        fig.set_size_inches(* NORMAL_FIGURE_SIZE)
    return send_figure_as_svg(fig, epic_name)
