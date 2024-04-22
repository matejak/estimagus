import wtforms

from ..base.forms import BaseForm


class DemoForm(BaseForm):
    issues = wtforms.SelectMultipleField('Issues')
    progress = wtforms.FloatField('Progress')
    submit = wtforms.SubmitField("Next Day")


class ResetForm(BaseForm):
    reset = wtforms.SubmitField("Reset Simulation")
