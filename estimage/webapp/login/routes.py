import flask
import flask_login

from . import bp
from . import forms

from .google_login import google_login
from ..users import User


def render_template(template_basename, title, **kwargs):
    authenticated_user = ""
    if flask_login.current_user.is_authenticated:
        authenticated_user = flask_login.current_user
    return flask.render_template(
        template_basename, title=title, authenticated_user=authenticated_user, ** kwargs)


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
    return render_template(
        'login.html', title='Sign In', login_form=form,
        next=safe_next_page, login_provider=login_provider)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    config_dict = flask.current_app.config

    next_page = flask.request.args.get('next')
    if not next_page or werkzeug.urls.url_parse(next_page).netloc != '':
        next_page = flask.url_for('main.tree_view')

    match provider_name := config_dict["LOGIN_PROVIDER_NAME"]:
        case "autologin":
            return autologin(next_page)
        case "google":
            return google_login(next_page)
        case _:
            msg = f"Unknown login provider: {provider_name}"
            raise ValueError(msg)

