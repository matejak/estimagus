import os

import flask
import flask_login

from ... import simpledata, persistence
from ...webapp import web_utils, routers
from . import forms
from .. import demo


bp = flask.Blueprint("demo", __name__, template_folder="templates")


def _get_card_loader(flavor, backend):
    card_class = flask.current_app.get_final_class("BaseCard")
    loader = type("loader", (flavor, persistence.SAVERS[card_class][backend], persistence.LOADERS[card_class][backend]), dict())
    return card_class, loader


def get_retro_loader():
    return _get_card_loader(simpledata.RetroCardIO, "ini")


def get_proj_loader():
    return _get_card_loader(simpledata.ProjCardIO, "ini")


@web_utils.is_primary_menu_of("demo", bp, "Estimagus Demo")
@bp.route('/demo', methods=("GET", "POST"))
@flask_login.login_required
def next_day():
    _, loader = get_retro_loader()

    start_date = flask.current_app.get_config_option("RETROSPECTIVE_PERIOD")[0]
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
    return flask.redirect(web_utils.head_url_for("demo.next_day"))
