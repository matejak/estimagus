import datetime

import flask
import flask_login

from ...webapp import web_utils
from ...plugins import crypto, jira, redhat_compliance
from ...plugins.jira import routes
from . import forms

bp = flask.Blueprint("crypto", __name__, template_folder="templates")


@web_utils.is_primary_menu_of("crypto", bp, "Red Hat Crypto")
@bp.route('/crypto', methods=("GET", "POST"))
@flask_login.login_required
def sync():
    form = forms.CryptoForm()
    if form.validate_on_submit():
        task_spec = crypto.InputSpec.from_form_and_app(form, flask.current_app)
        jira.routes.do_stuff_and_flash_messages(task_spec, crypto.do_stuff)
    else:
        next_starts_soon = redhat_compliance.days_to_next_epoch(datetime.datetime.today()) < 30
        form.project_next.data = next_starts_soon
    return web_utils.render_template(
        'crypto.html', title='Red Hat Crypto Plugin', plugin_form=form, )
