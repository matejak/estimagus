import datetime

import flask
import flask_login

from ...webapp import web_utils
from ...plugins import jira, redhat_compliance
from ...plugins.jira import routes
from . import forms

bp = flask.Blueprint("rhcompliance", __name__, template_folder="templates")


@web_utils.is_primary_menu_of("redhat_compliance", bp, "Red Hat Compliance")
@bp.route('/rhcompliance', methods=("GET", "POST"))
@flask_login.login_required
def sync():
    form = forms.RedhatComplianceForm()
    if form.validate_on_submit():
        form.perform_work_with_token_encryption()
        task_spec = redhat_compliance.InputSpec.from_form_and_app(form, flask.current_app)
        jira.routes.do_stuff_and_flash_messages(task_spec, redhat_compliance.do_stuff)
    else:
        form.quarter.data = redhat_compliance.datetime_to_epoch(datetime.datetime.today())
        next_starts_soon = redhat_compliance.days_to_next_epoch(datetime.datetime.today()) < 30
        form.project_next.data = next_starts_soon

    return web_utils.render_template(
        'rhcompliance.html', title='Red Hat Compliacne Plugin', plugin_form=form, )
