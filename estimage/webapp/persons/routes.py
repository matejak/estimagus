import io
import datetime

import flask
import flask_login

from . import bp
from .. import web_utils
from ... import persons, utilities


@bp.route('/projective_workload')
@flask_login.login_required
def projective_workload():
    user = flask_login.current_user
    user_id = user.get_id()

    all_targets_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    all_targets = list(all_targets_by_id.values())
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)

    simple_workloads_type = web_utils.get_workloads(persons.SimpleWorkloads)
    simple_workloads = simple_workloads_type(targets_tree_without_duplicates, model)
    simple_workloads.solve_problem()
    simple_summary = simple_workloads.summary()
    all_persons = sorted(simple_workloads.persons_potential.keys())

    summaries_and_workloads = dict(
        simple_summary=simple_summary, simple=simple_workloads,
        )
    optimized_workloads_type = web_utils.get_workloads(persons.OptimizedWorkloads)
    optimized_workloads = optimized_workloads_type(targets_tree_without_duplicates, model)
    try:
        optimized_workloads.solve_problem()
        optimized_summary = optimized_workloads.summary()
        summaries_and_workloads["optimized"] = optimized_workloads
        summaries_and_workloads["optimized_summary"] = optimized_summary
    except ValueError as exc:
        optimized_workloads = None
        flask.flash(f"Error optimizing workload: {exc}")

    return web_utils.render_template(
        'workload.html', title='Projective Workloads', all_persons=all_persons,
        ** summaries_and_workloads
    )
