from flask_wtf import FlaskForm
import wtforms
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class Promotion(FlaskForm):
    def __init__(self, serious_note, button_msg, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.i_kid_you_not.label.text = serious_note
        self.submit.label.text = button_msg

    i_kid_you_not = BooleanField("I am serious")
    submit = SubmitField("Approve")


class ConsensusForm(Promotion):
    def __init__(self, * args, ** kwargs):
        serious_note = "Own Estimate Represents the Consensus"
        button_msg = "Promote Own Estimate"
        super().__init__(* args, serious_note=serious_note, button_msg=button_msg, ** kwargs)


class AuthoritativeForm(Promotion):
    def __init__(self, * args, ** kwargs):
        serious_note = "Consensus Represents should be authoritative"
        button_msg = "Promote Consensus Estimate"
        super().__init__(* args, serious_note=serious_note, button_msg=button_msg, ** kwargs)


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
