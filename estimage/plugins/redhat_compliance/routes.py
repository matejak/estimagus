import datetime

import flask
import flask_login

from ...webapp import web_utils
from ...plugins import redhat_compliance
from . import forms

bp = flask.Blueprint("rhcompliance", __name__, template_folder="templates")


@bp.route('/rhcompliance', methods=("GET", "POST"))
@flask_login.login_required
def sync():

    form = forms.RedhatComplianceForm()
    if form.validate_on_submit():

        task_spec = redhat_compliance.InputSpec.from_form_and_app(form, flask.current_app)

        retro_loader = web_utils.get_retro_loader()[1]
        proj_loader = web_utils.get_proj_loader()[1]

        redhat_compliance.do_stuff(task_spec, retro_loader, proj_loader)
    else:
        form.quarter.data = redhat_compliance.datetime_to_epoch(datetime.datetime.today())
        next_starts_soon = redhat_compliance.days_to_next_epoch(datetime.datetime.today()) < 20
        form.project_next.data = next_starts_soon

    return web_utils.render_template(
        'rhcompliance.html', title='Red Hat Compliacne Plugin', plugin_form=form, )
