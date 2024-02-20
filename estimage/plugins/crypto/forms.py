from flask_wtf import FlaskForm
import wtforms


from ..jira import forms


class CryptoFormEnd(FlaskForm):
    submit = wtforms.SubmitField("Import Data")


class CryptoForm(forms.EncryptedTokenForm, CryptoFormEnd):
    pass
