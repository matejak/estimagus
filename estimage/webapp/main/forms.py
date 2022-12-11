from flask_wtf import FlaskForm
import wtforms
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


class PromotionMixin(FlaskForm):
    def __init__(self, id_prefix, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.i_kid_you_not.id = id_prefix + self.i_kid_you_not.id
        self.submit.id = id_prefix + self.submit.id


class ConsensusForm(PromotionMixin):
    def __init__(self, * args, ** kwargs):
        id_prefix = "consensus_"
        super().__init__(* args, id_prefix=id_prefix, ** kwargs)

    i_kid_you_not = BooleanField("Own Estimate Represents the Consensus")
    forget_own_estimate = BooleanField("Also Forget Own Estimate", default=True)
    submit = SubmitField("Promote Own Estimate")


class AuthoritativeForm(PromotionMixin):
    def __init__(self, * args, ** kwargs):
        id_prefix = "authoritative_"
        super().__init__(* args, id_prefix=id_prefix, ** kwargs)

    i_kid_you_not = BooleanField("Consensus should be authoritative")
    submit = SubmitField("Promote Consensus Estimate")


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
