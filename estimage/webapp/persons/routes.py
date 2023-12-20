import io
import datetime

import flask
import flask_login

from . import bp
from .. import web_utils
from ... import persons, utilities


def render_workload(title, mode, cards_tree, model):
    simple_workloads_type = web_utils.get_workloads(persons.SimpleWorkloads)
    simple_workloads = simple_workloads_type(cards_tree, model)
    simple_workloads.solve_problem()
    simple_summary = simple_workloads.summary()
    all_persons = sorted(simple_workloads.persons_potential.keys())

    summaries_and_workloads = dict(
        simple_summary=simple_summary, simple=simple_workloads,
        )
    optimized_workloads_type = web_utils.get_workloads(persons.OptimizedWorkloads)
    optimized_workloads = optimized_workloads_type(cards_tree, model)
    try:
        optimized_workloads.solve_problem()
        optimized_summary = optimized_workloads.summary()
        summaries_and_workloads["optimized"] = optimized_workloads
        summaries_and_workloads["optimized_summary"] = optimized_summary
    except ValueError as exc:
        optimized_workloads = None
        flask.flash(f"Error optimizing workload: {exc}")

    return web_utils.render_template(
        'workload.html', title=title, all_persons=all_persons, mode=mode,
        ** summaries_and_workloads
    )


@bp.route('/retrospective_workload')
@flask_login.login_required
def retrospective_workload():
    user = flask_login.current_user
    user_id = user.get_id()

    all_cards_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    all_cards = list(all_cards_by_id.values())
    cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_cards)
    return render_workload('Retrospective Workloads', "retro", cards_tree_without_duplicates, model)


@bp.route('/planning_workload')
@flask_login.login_required
def planning_workload():
    user = flask_login.current_user
    user_id = user.get_id()

    all_cards_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("proj", user_id)
    all_cards = list(all_cards_by_id.values())
    cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_cards)
    return render_workload('Planning Workloads', "plan", cards_tree_without_duplicates, model)
