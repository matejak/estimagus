from flask_wtf import FlaskForm
import wtforms


class RedhatComplianceForm(FlaskForm):
    token = wtforms.PasswordField('Token')
    quarter = wtforms.StringField('Quarter String')
    submit = wtforms.SubmitField("Import Data")
