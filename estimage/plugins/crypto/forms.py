from ..base.forms import BaseForm
import wtforms


from ..jira import forms


class CryptoFormEnd(BaseForm):
    project_next = wtforms.BooleanField('Plan for the Next Iteration')
    submit = wtforms.SubmitField("Import Data")


class CryptoForm(forms.EncryptedTokenForm, CryptoFormEnd):
    pass
