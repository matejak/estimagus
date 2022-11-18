from flask_wtf import FlaskForm
import wtforms
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class ConsensusForm(FlaskForm):
    i_kid_you_not = BooleanField("Own Estimate Represents the Consensus")
    submit = SubmitField("Approve")


FIB = [0, 1, 2, 3, 5, 8, 13, 21, 34]


class NumberEstimationForm(FlaskForm):
    optimistic = wtforms.DecimalField("Optimistic")
    most_likely = wtforms.DecimalField("Most Likely")
    pessimistic = wtforms.DecimalField("Pessimistic")
    submit = SubmitField("Save Estimate")


class PointEstimationForm(FlaskForm):
    optimistic = wtforms.SelectField("Optimistic", choices=FIB)
    most_likely = wtforms.SelectField("Most Likely", choices=FIB)
    pessimistic = wtforms.SelectField("Pessimistic", choices=FIB)
    submit = SubmitField("Save Estimate")
