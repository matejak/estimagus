import flask
import flask_login

from . import bp
from . import forms

from .google_login import google_login, google_auto_login
from ..users import User
from .. import web_utils


@bp.route('/logout', methods=['GET'])
def logout():
    flask_login.logout_user()
    return flask.redirect(flask.url_for("login.login"))


def autologin(safe_next_page):
    form = forms.AutoLoginForm()
    if form.validate_on_submit():
        user = User(form.username.data)
        flask_login.login_user(user, remember=form.remember_me.data)
        return flask.redirect(safe_next_page)
    login_provider = flask.current_app.config["LOGIN_PROVIDER_NAME"]
    return web_utils.render_template(
        'login.html', title='Sign In', login_form=form,
        next=safe_next_page, login_provider=login_provider)


def perform_login_selection(login_methods, login_description):
    config_dict = flask.current_app.config

    next_page = flask.request.args.get('next')
    safe_next_page = web_utils.safe_url_to_redirect(next_page)

    provider_name = config_dict["LOGIN_PROVIDER_NAME"]
    if provider_name not in login_methods:
        msg = f"Unknown login provider '{provider_name}' for {login_description}"
        raise ValueError(msg)
    return login_methods[provider_name](safe_next_page)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    login_methods = dict(
        autologin=autologin,
        google=google_login,
    )
    return perform_login_selection(login_methods, "interactive login")


@bp.route('/autologin', methods=['GET', 'POST'])
def auto_login():
    login_methods = dict(
        autologin=autologin,
        google=google_auto_login,
    )
    return perform_login_selection(login_methods, "automatic login")
