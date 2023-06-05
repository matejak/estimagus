import flask
import flask_login

from ...webapp import web_utils
from ...plugins import jira
from . import forms

bp = flask.Blueprint("jira", __name__, template_folder="templates")


@bp.route('/jira', methods=("GET", "POST"))
@flask_login.login_required
def jira_plugin():
    form = forms.JiraForm()
    if form.validate_on_submit():

        task_spec = jira.InputSpec.from_form_and_app(form, flask.current_app)
        jira.do_stuff(task_spec)

    return web_utils.render_template(
        'jira.html', title='Jira Plugin', plugin_form=form, )
