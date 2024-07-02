import flask
import flask_login

from ...webapp import web_utils
from . import forms
from .. import redhat_jira, jira


bp = flask.Blueprint("redhat_jira", __name__, template_folder="templates")


@web_utils.is_primary_menu_of("redhat_jira", bp, "Red Hat Jira")
@bp.route('/redhat_jira', methods=("GET", "POST"))
@flask_login.login_required
def sync():
    app = flask.current_app
    form = redhat_jira.forms.RedhatJiraForm()
    if form.validate_on_submit():
        task_spec = redhat_jira.InputSpec.from_form_and_app(form, flask.current_app)
        jira.routes.do_stuff_and_flash_messages(task_spec, redhat_jira.do_stuff)
    else:
        form.cutoffDate.data = app.get_config_option("RETROSPECTIVE_PERIOD")[0]
    return web_utils.render_template(
        'jira.html', title='Red Hat Jira Plugin', plugin_form=form, )
