from flask_wtf import FlaskForm
import wtforms


class JiraForm(FlaskForm):
    server = wtforms.StringField('Server URL', default="https://")
    token = wtforms.PasswordField('Token')
    retroQuery = wtforms.StringField('Retrospective Query')
    projQuery = wtforms.StringField('Projective Query')
    cutoffDate = wtforms.DateField("History Cutoff date")
    submit = wtforms.SubmitField("Import Data")
