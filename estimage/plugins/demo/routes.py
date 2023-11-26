import os

import flask
import flask_login

from ...webapp import web_utils
from . import forms
from .. import demo

bp = flask.Blueprint("demo", __name__, template_folder="templates")


@bp.route('/demo', methods=("GET", "POST"))
@flask_login.login_required
def next_day():
    user = flask_login.current_user
    user_id = user.get_id()

    cls, loader = web_utils.get_retro_loader()
    targets_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)

    start_date = flask.current_app.config["RETROSPECTIVE_PERIOD"][0]
    doer = demo.Demo(loader, start_date)
    doer.start_if_on_start()

    form = forms.DemoForm()
    form.issues.choices = doer.get_sensible_choices()

    if form.validate_on_submit():
        doer.apply_work(form.progress.data, form.issues.data)

    form.issues.choices = doer.get_actual_choices()

    return web_utils.render_template(
        'demo.html', title='Demo Plugin', reset_form=forms.ResetForm(), plugin_form=form, day_index=doer.day_index)


@bp.route('/reset', methods=("POST", ))
@flask_login.login_required
def reset():
    reset_form = forms.ResetForm()
    if reset_form.validate_on_submit():
        demo.reset_data()
    return flask.redirect(flask.url_for("demo.next_day"))
