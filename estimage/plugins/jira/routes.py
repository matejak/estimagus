import flask
import flask_login

from ...webapp import web_utils
from .. import jira
from . import forms

bp = flask.Blueprint("jira", __name__, template_folder="templates")


def try_callback_and_produce_error_msg(argument, callback):
    error_msg = ""
    try:
        stats = callback(argument)
        flask.flash(jira.stats_to_summary(stats))
    except jira.exceptions.JIRAError as exc:
        if 500 <= exc.status_code < 600:
            error_msg = f"Error {exc.status_code} when interacting with Jira, accessing URL {exc.url}"
        else:
            error_msg = f"Error {exc.status_code} when interacting with Jira: {exc.text}"
    except RuntimeError as exc:
        error_msg = str(exc)
    return error_msg


def do_stuff_and_flash_messages(task_spec, callback):
    error_msg = try_callback_and_produce_error_msg(task_spec, callback)

    if "auth" in error_msg:
        error_msg += " Perhaps there is a typo in the token, or the token expired?"

    if error_msg:
        flask.flash(error_msg)


@bp.route('/jira', methods=("GET", "POST"))
@flask_login.login_required
def jira_plugin():
    form = forms.JiraForm()
    if form.validate_on_submit():
        form.perform_work_with_token_encryption()

        task_spec = jira.InputSpec.from_form_and_app(form, flask.current_app)

        do_stuff_and_flash_messages(task_spec, jira.do_stuff)

    return web_utils.render_template(
        'jira.html', title='Jira Plugin', plugin_form=form, )
