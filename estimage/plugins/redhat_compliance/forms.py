from flask_wtf import FlaskForm
import wtforms

from ..jira import forms


class RedhatComplianceFormEnd(FlaskForm):
    quarter = wtforms.StringField('Quarter String')
    project_next = wtforms.BooleanField('Plan for the Next Quarter')
    submit = wtforms.SubmitField("Import Data")


class RedhatComplianceForm(forms.EncryptedTokenForm, RedhatComplianceFormEnd):
    pass


class RedhatComplianceRefreshForm(FlaskForm):

    def request_refresh_of(self, names):
        self.cards.data = ",".join(names)
        if len(names) == 1:
            self.submit.label.text = "Refresh item"
        elif (count := len(names)) > 1:
            self.submit.label.text = f"Refresh total {count} items"

    def get_what_names_to_refresh(self):
        return self.cards.data.split(",")

    token = wtforms.PasswordField('Token')
    mode = wtforms.HiddenField('retro_or_proj')
    cards = wtforms.HiddenField('csv')
    next = wtforms.HiddenField('url')
    submit = wtforms.SubmitField("Refresh")


class AuthoritativeForm(forms.EncryptedTokenForm):
    token = wtforms.PasswordField('Jira Token')

    def clear_to_go(self):
        self.enable_submit_button()
        super().clear_to_go()

    def __iter__(self):
        attributes = (
            self.csrf_token,
            self.task_name,
            self.point_cost,
            self.token,
            self.store_token,
            self.i_kid_you_not,
            self.encrypted_token,
            self.encrypted_meant_for_storage,
            self.submit,
        )
        ret = (a for a in attributes)
        return ret
