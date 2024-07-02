from ..base.forms import BaseForm
import wtforms


from ..jira import forms


class RedhatJiraFormEnd(BaseForm):
    retroQuery = wtforms.StringField('Retrospective Query')
    projQuery = wtforms.StringField('Projective Query')
    cutoffDate = wtforms.DateField("History Cutoff date")
    submit = wtforms.SubmitField("Import Data")


class RedhatJiraForm(forms.EncryptedTokenForm, RedhatJiraFormEnd):
    pass

