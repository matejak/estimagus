import datetime

import flask
import flask_login

from . import forms
from ...webapp import web_utils, routers
from ...webapp.main import cards

bp = flask.Blueprint("wsjf", __name__, template_folder="templates")


def _update_card_priority(card_name, io_cls, form):
    card_cls = flask.current_app.get_final_class("BaseCard")
    card = card_cls.load_metadata(card_name, io_cls)
    card.business_value = form.business_value.data
    card.risk_and_opportunity = form.risk_and_opportunity.data
    card.time_sensitivity = form.time_sensitivity.data
    card.save_metadata(io_cls)


@bp.route('/prioritize/<task_name>', methods=("POST",))
@flask_login.login_required
def prioritize(task_name):
    form = forms.WSJFForm()
    if form.validate_on_submit():
        io_cls = routers.IORouter().get_card_io("proj")
        _update_card_priority(task_name, io_cls, form)
        routers.CardRouter.clear_cache()
    form.task_name.data = task_name

    return cards.view_projective_task(task_name=task_name, known_forms=dict(wsjf=form))
