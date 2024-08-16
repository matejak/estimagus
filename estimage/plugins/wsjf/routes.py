import datetime

import flask
import flask_login

from . import forms

bp = flask.Blueprint("wsjf", __name__, template_folder="templates")


@bp.route('/prioritize', methods=("POST",))
@flask_login.login_required
def sync():
    form = forms.WSJFForm()
    if form.validate_on_submit():
        pass

    return flask.url_for()
