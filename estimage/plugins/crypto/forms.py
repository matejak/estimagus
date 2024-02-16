from flask_wtf import FlaskForm
import wtforms


class CryptoForm(FlaskForm):
    token = wtforms.PasswordField('Token')
    store_token = wtforms.BooleanField('Store Token Locally for Later', default=True)
    encrypted_token = wtforms.HiddenField('Encrypted Token')
    encrypted_meant_for_storage = wtforms.HiddenField('Store the Encrypted Token', default="no")
    submit = wtforms.SubmitField("Import Data")

