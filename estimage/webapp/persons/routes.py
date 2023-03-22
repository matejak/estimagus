import io
import datetime

import flask
import flask_login

from . import bp
from .. import web_utils
from ... import persons
from ... import simpledata as webdata


@bp.route('/projective_workload')
@flask_login.login_required
def projective_workload():
    user = flask_login.current_user

    user_id = user.get_id()
    all_targets = webdata.ProjTarget.get_loaded_targets_by_id()
    model = web_utils.get_user_model(user_id, webdata.ProjTarget)

    workloads = persons.get_all_workloads(all_targets.values(), model)
    if "" in workloads:
        workloads.pop("")
    all_persons = sorted(workloads.keys())

    return web_utils.render_template(
        'workload.html', title='Projective Workloads', all_persons=all_persons, workloads=workloads)
