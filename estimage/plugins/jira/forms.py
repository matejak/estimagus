import base64
import hashlib
import textwrap

import cryptography.fernet
import flask
import wtforms

from ..base.forms import BaseForm


class JiraFormStart(BaseForm):
    server = wtforms.StringField('Server URL', default="https://")


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


class EncryptedTokenForm(BaseForm):
    token = wtforms.PasswordField('Token')
    store_token = wtforms.BooleanField('Store token locally for later', default=True)
    encrypted_token = wtforms.HiddenField('Encrypted Token')
    encrypted_meant_for_storage = wtforms.HiddenField('Store the Encrypted Token', default="no")
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self.extending_fields.append(self.token)
        self.extending_fields.append(self.store_token)

    def validate_on_submit(self):
        ret = super().validate_on_submit()
        if ret:
            self._perform_work_with_token_encryption()
        return ret

    def _perform_work_with_token_encryption(self):
        if not self.token.data and self.encrypted_token.data:
            self.token.data = decrypt_stuff(self.encrypted_token.data)
        if self.store_token.data:
            self.encrypted_token.data = encrypt_stuff(self.token.data)
            self.encrypted_meant_for_storage.data = "yes"


class JiraFormEnd(BaseForm):
    retroQuery = wtforms.StringField('Retrospective Query')
    projQuery = wtforms.StringField('Projective Query')
    cutoffDate = wtforms.DateField("History Cutoff date")
    submit = wtforms.SubmitField("Import Data")


class JiraForm(JiraFormStart, EncryptedTokenForm, JiraFormEnd):
    pass
