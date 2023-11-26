from flask_wtf import FlaskForm
import wtforms


class DemoForm(FlaskForm):
    issues = wtforms.SelectMultipleField('Issues')
    progress = wtforms.FloatField('Progress')
    submit = wtforms.SubmitField("Next Day")


class ResetForm(FlaskForm):
    reset = wtforms.SubmitField("Reset Simulation")
