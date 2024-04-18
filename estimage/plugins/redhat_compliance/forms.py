import wtforms

from ..jira import forms
from ..base.forms import BaseForm


class RedhatComplianceFormEnd(BaseForm):
    quarter = wtforms.StringField('Quarter String')
    project_next = wtforms.BooleanField('Plan for the Next Quarter')
    submit = wtforms.SubmitField("Import Data")


class RedhatComplianceForm(forms.EncryptedTokenForm, RedhatComplianceFormEnd):
    pass
