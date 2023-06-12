from flask_wtf import FlaskForm
import wtforms


class DemoForm(FlaskForm):
    issues = wtforms.RadioField('Issues')
    progress = wtforms.FloatField('Progress')
    submit = wtforms.SubmitField("Next Day")
