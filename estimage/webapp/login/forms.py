from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField
from wtforms.validators import DataRequired


class AutoLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class GoogleLoginForm(FlaskForm):
    submit = SubmitField('Sign In using Google')


LOGIN_FORMS = dict(
    autologin=AutoLoginForm,
    google=GoogleLoginForm,
)


