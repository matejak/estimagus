import flask
import flask_login
import requests
import json
import urllib.parse

from oauthlib import oauth2

from . import bp
from . import forms
from ..users import User


def get_google_client(app):
    GOOGLE_CLIENT_ID = flask.current_app.config["GOOGLE_CLIENT_ID"]
    return oauth2.WebApplicationClient(GOOGLE_CLIENT_ID)


def get_google_provider_cfg():
    GOOGLE_DISCOVERY_URL = flask.current_app.config["GOOGLE_DISCOVERY_URL"]
    return requests.get(GOOGLE_DISCOVERY_URL, timeout=10).json()


def encode_data_urlsafe(** kwargs):
    unsafe_str = json.dumps(kwargs)
    return urllib.parse.quote_plus(unsafe_str)


def decode_urlsafe_data(safe_string):
    dumped = urllib.parse.unquote_plus(safe_string)
    return json.loads(dumped)


@bp.route('/google_login')
def google_login(safe_next_page):
    form = forms.GoogleLoginForm()
    if form.validate_on_submit():
        return start_google_login(safe_next_page)

    login_provider = flask.current_app.config["LOGIN_PROVIDER_NAME"]
    return flask.render_template(
        'login.html', title='Sign In', login_form=form,
        next=safe_next_page, login_provider=login_provider)


@bp.route('/google_auto_login')
def google_auto_login(safe_next_page):
    return start_google_login(safe_next_page)


def start_google_login(safe_next_page):
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    client = get_google_client(flask.app)

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=flask.request.base_url + "/callback",
        scope=["openid", "email"],
        state=encode_data_urlsafe(safe_next_page=safe_next_page)
    )
    return flask.redirect(request_uri)


@bp.route('/login/callback', methods=['GET', 'POST'])
def google_callback_dest():
    client = get_google_client(flask.app)
    GOOGLE_CLIENT_ID = flask.current_app.config["GOOGLE_CLIENT_ID"]
    GOOGLE_CLIENT_SECRET = flask.current_app.config["GOOGLE_CLIENT_SECRET"]

    google_auth_code = flask.request.args.get("code")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    state_object = decode_urlsafe_data(flask.request.args.get("state"))
    token_endpoint = google_provider_cfg["token_endpoint"]

    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=flask.request.url,
        redirect_url=flask.request.base_url,
        code=google_auth_code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        timeout=10,
    )
    client.parse_request_body_response(json.dumps(token_response.json()))
    try:
        mail = _get_user_email(client)
    except Exception as exc:
        return str(exc), 400

    user, domain = mail.split("@", 1)
    user = User(user, domain)
    flask_login.login_user(user)
    return flask.redirect(state_object["safe_next_page"])


def _get_user_email(client):
    google_provider_cfg = get_google_provider_cfg()

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body, timeout=10)

    response_json = userinfo_response.json()
    if not response_json.get("email_verified"):
        msg = "User email not available or not verified by Google."
        return ValueError(msg)

    users_email = response_json["email"]
    return users_email
