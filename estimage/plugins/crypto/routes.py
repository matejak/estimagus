import base64
import datetime
import hashlib

import flask
import cryptography.fernet
import flask_login

from ...webapp import web_utils
from ...plugins import crypto
from . import forms

bp = flask.Blueprint("crypto", __name__, template_folder="templates")


def get_fernet():
    flask_secret_key_encoded = flask.current_app.config["SECRET_KEY"].encode()
    key = hashlib.scrypt(flask_secret_key_encoded, salt=flask_secret_key_encoded, n=1024, r=8, p=1, dklen=32)
    encoded_key = base64.urlsafe_b64encode(key)
    return cryptography.fernet.Fernet(encoded_key)


def decrypt_stuff(what):
    fernet = get_fernet()
    return fernet.decrypt(what.encode()).decode()


def encrypt_stuff(what):
    fernet = get_fernet()
    return fernet.encrypt(what.encode()).decode()


@web_utils.is_primary_menu_of("crypto", bp, "Red Hat Crypto")
@bp.route('/crypto', methods=("GET", "POST"))
@flask_login.login_required
def sync():
    form = forms.CryptoForm()
    if form.validate_on_submit():
        if not form.token.data and form.encrypted_token.data:
            form.token.data = decrypt_stuff(form.encrypted_token.data)
        if form.store_token.data:
            form.encrypted_token.data = encrypt_stuff(form.token.data)
            form.encrypted_meant_for_storage.data = "yes"
        task_spec = crypto.InputSpec.from_form_and_app(form, flask.current_app)
        crypto.do_stuff(task_spec)
    return web_utils.render_template(
        'crypto.html', title='Red Hat Crypto Plugin', plugin_form=form, )
