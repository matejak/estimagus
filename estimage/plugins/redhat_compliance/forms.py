from flask_wtf import FlaskForm
import wtforms


class RedhatComplianceForm(FlaskForm):
    token = wtforms.PasswordField('Token')
    quarter = wtforms.StringField('Quarter String')
    submit = wtforms.SubmitField("Import Data")


class RedhatComplianceRefreshForm(FlaskForm):

    def request_refresh_of(self, names):
        self.targets.data = ",".join(names)
        if len(names) == 1:
            self.submit.label.text = "Refresh item"
        elif (count := len(names)) > 1:
            self.submit.label.text = f"Refresh total {count} items"

    def get_what_names_to_refresh(self):
        return self.targets.data.split(",")

    token = wtforms.PasswordField('Token')
    mode = wtforms.HiddenField('retro_or_proj')
    targets = wtforms.HiddenField('csv')
    next = wtforms.HiddenField('url')
    submit = wtforms.SubmitField("Refresh")


class AuthoritativeForm:
    token = wtforms.PasswordField('Jira Token')

    def clear_to_go(self):
        self.enable_submit_button()
        super().clear_to_go()
