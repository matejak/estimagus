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

        retro_io = web_utils.get_retro_loader()[1]
        proj_io = web_utils.get_proj_loader()[1]

        try:
            stats = jira.do_stuff(task_spec, retro_io, proj_io)
            flask.flash(jira.stats_to_summary(stats))
        except RuntimeError as exc:
            error_msg = str(exc)

        if error_msg:
            flask.flash(error_msg)

    return web_utils.render_template(
        'jira.html', title='Jira Plugin', plugin_form=form, )
