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

    workloads = persons.get_all_workloads(targets_tree_without_duplicates, model)
    if "" in workloads:
        workloads.pop("")
    all_persons = sorted(workloads.keys())

    workloadss = persons.Workloads(targets_tree_without_duplicates, model)
    workloadss.collaborators_potential["ggasparb"] = 0.2
    workloadss.collaborators_potential["mmarhefk"] = 0.2
    workloadss.collaborators_potential["jjaburek"] = 0.6
    workloadss.collaborators_potential["matyc"] = 0.4
    workloadss.collaborators_potential["rh-ee-acortes"] = 0.6
    workloadss.solve_problem()

    return web_utils.render_template(
        'workload.html', title='Projective Workloads', all_persons=all_persons, workloads=workloads, modeled_workloads=workloadss)
