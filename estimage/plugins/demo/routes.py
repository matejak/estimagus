import os

import flask
import flask_login

from ... import simpledata, persistence
from ...webapp import web_utils, routers
from . import forms
from .. import demo


bp = flask.Blueprint("demo", __name__, template_folder="templates")


def get_retro_loader():
    router = routers.CardRouter(mode="retro")
    return router.cards_io


def get_proj_loader():
    return router.cards_io


@web_utils.is_primary_menu_of("demo", bp, "Estimagus Demo")
@bp.route('/demo', methods=("GET", "POST"))
@flask_login.login_required
def next_day():
    router = routers.IORouter()
    retro_card_io = router.get_card_io("retro")

    start_date = flask.current_app.get_config_option("RETROSPECTIVE_PERIOD")[0]
    doer = demo.Demo(start_date, retro_card_io, router.get_storage_io(), router.get_event_io())
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
    router = routers.IORouter()
    reset_form = forms.ResetForm()
    if reset_form.validate_on_submit():
        demo.reset_data(router.get_storage_io(), router.get_event_io())
    return flask.redirect(web_utils.head_url_for("demo.next_day"))
