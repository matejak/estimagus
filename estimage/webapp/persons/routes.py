import io
import datetime

import flask
import flask_login

from . import bp
from .. import web_utils
from ... import persons, utilities
from ... import simpledata as webdata


@bp.route('/projective_workload')
@flask_login.login_required
def projective_workload():
    user = flask_login.current_user

    user_id = user.get_id()
    all_targets = webdata.ProjTarget.get_loaded_targets_by_id()
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(list(all_targets.values()))
    model = web_utils.get_user_model(user_id, webdata.ProjTarget)

    simple_workloads = persons.SimpleWorkloads(targets_tree_without_duplicates, model)
    all_persons = sorted(simple_workloads.persons_potential.keys())

    optimized_workloads = persons.OptimizedWorkloads(targets_tree_without_duplicates, model)
    try:
        optimized_workloads.solve_problem()
    except ValueError as exc:
        optimized_workloads = None
        flask.flash(f"Error optimizing workload: {exc}")

    return web_utils.render_template(
        'workload.html', title='Projective Workloads', all_persons=all_persons,
        simple=simple_workloads, optimized=optimized_workloads)
