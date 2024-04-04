from flask_wtf import FlaskForm
import wtforms


from ..jira import forms


class CryptoFormEnd(FlaskForm):
    project_next = wtforms.BooleanField('Plan for the Next Iteration')
    submit = wtforms.SubmitField("Import Data")


class CryptoForm(forms.EncryptedTokenForm, CryptoFormEnd):
    pass


class ProblemForm(forms.EncryptedTokenForm):
    pass
