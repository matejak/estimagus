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

    @classmethod
    def supporting_js(cls, forms):
        template = textwrap.dedent("""
        <script type="text/javascript">
        function tokenName() {
            return "estimagus." + location.hostname + ".jira_ePAT";
        }

        function getPAT() {
            const token_name = tokenName();
            return localStorage.getItem(token_name);
        }

        function updatePAT(with_what) {
            const token_name = tokenName();
            return localStorage.setItem(token_name, with_what);
        }

        function supplyEncryptedToken(encrypted_field, normal_field, store_checkbox, token_str) {
            store_checkbox.checked = false;
            encrypted_field.value = token_str;
            normal_field.placeholder = "Optional, using stored locally stored token by default";
        }

        const prefixes = %s;
        prefixes.forEach(function(prefix) {
            let update_store = document.getElementById(prefix + 'encrypted_meant_for_storage');
            let enc_field = document.getElementById(prefix + 'encrypted_token');
            if (update_store.value == "yes" && enc_field.value) {
                  updatePAT(enc_field.value);
            }
        });

        let pat = getPAT();
        if (pat) {
            prefixes.forEach(function(prefix) {
                let normal_field = document.getElementById(prefix + 'token');
                let store_checkbox = document.getElementById(prefix + 'store_token');
                let enc_field = document.getElementById(prefix + 'encrypted_token');
                supplyEncryptedToken(enc_field, normal_field, store_checkbox, pat);
            });
        }
        </script>
        """)
        prefixes = [f._prefix for f in forms]
        return template % prefixes


class JiraFormEnd(BaseForm):
    retroQuery = wtforms.StringField('Retrospective Query')
    projQuery = wtforms.StringField('Projective Query')
    cutoffDate = wtforms.DateField("History Cutoff date")
    submit = wtforms.SubmitField("Import Data")


class JiraForm(JiraFormStart, EncryptedTokenForm, JiraFormEnd):
    pass
