import datetime
import collections

import flask
import flask_login

from . import bp
from . import forms
from .. import web_utils


@bp.route('/')
@flask_login.login_required
def index():
    user = flask_login.current_user
    user_id = user.get_id()

    summaries = get_heads_summaries()

    return web_utils.render_template(
        "portal.html",
        title="Available Heads",
        summaries=summaries)


def get_heads_summaries():
    summaries = dict()
    for name in flask.current_app.config.get("head", frozenset()):
        summaries[name] = flask.current_app.config["head"][name].get("description")
    return summaries
