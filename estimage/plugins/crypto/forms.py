from flask_wtf import FlaskForm
import wtforms


class CryptoForm(FlaskForm):
    token = wtforms.PasswordField('Token')
    submit = wtforms.SubmitField("Import Data")

