import wtforms

from ..jira import forms
from ..base.forms import BaseForm


class RedhatComplianceFormEnd(BaseForm):
    quarter = wtforms.StringField('Retrospective Quarter String')
    planning_quarter = wtforms.StringField('Planning Quarter String')
    submit = wtforms.SubmitField("Import Data")


class RedhatComplianceForm(forms.EncryptedTokenForm, RedhatComplianceFormEnd):
    pass
