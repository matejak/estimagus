from flask_wtf import FlaskForm
import wtforms
from wtforms import StringField, BooleanField, SubmitField, PasswordField


class SubmitMixin:
    def enable_submit_button(self):
        if self.submit.render_kw is not None:
            self.submit.render_kw.pop("disabled")

    def disable_submit_button(self):
        if self.submit.render_kw is None:
            self.submit.render_kw = dict(disabled="disabled")
        self.submit.render_kw["disabled"] = "disabled"


class DeleteMixin:
    def enable_delete_button(self):
        if self.delete.render_kw is not None:
            self.delete.render_kw.pop("disabled")

    def disable_delete_button(self):
        if self.delete.render_kw is None:
            self.delete.render_kw = dict(disabled="disabled")
        self.delete.render_kw["disabled"] = "disabled"


class PromotionMixin(FlaskForm):
    def __init__(self, id_prefix, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.i_kid_you_not.id = id_prefix + self.i_kid_you_not.id
        self.submit.id = id_prefix + self.submit.id
        self.disable_submit_button()


class ConsensusForm(PromotionMixin, SubmitMixin, DeleteMixin):
    i_kid_you_not = BooleanField("Own Estimate Represents the Consensus")
    forget_own_estimate = BooleanField("Also Forget Own Estimate", default=True)
    submit = SubmitField("Promote Own Estimate")
    delete = SubmitField("Forget Consensus")

    def __init__(self, * args, ** kwargs):
        id_prefix = "consensus_"
        super().__init__(* args, id_prefix=id_prefix, ** kwargs)
        self.disable_delete_button()


class AuthoritativeForm(PromotionMixin, SubmitMixin):
    def __init__(self, * args, ** kwargs):
        id_prefix = "authoritative_"
        super().__init__(* args, id_prefix=id_prefix, ** kwargs)

    i_kid_you_not = BooleanField("Consensus should be authoritative")
    submit = SubmitField("Promote Consensus Estimate")


FIB = [0, 1, 2, 3, 5, 8, 13, 21, 34]


class NumberEstimationForm(FlaskForm, SubmitMixin, DeleteMixin):
    optimistic = wtforms.DecimalField("Optimistic")
    most_likely = wtforms.DecimalField("Most Likely")
    pessimistic = wtforms.DecimalField("Pessimistic")
    submit = SubmitField("Save Estimate")
    delete = SubmitField("Forget Estimate")

    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.disable_delete_button()


class PointEstimationForm(FlaskForm):
    optimistic = wtforms.SelectField("Optimistic", choices=FIB)
    most_likely = wtforms.SelectField("Most Likely", choices=FIB)
    pessimistic = wtforms.SelectField("Pessimistic", choices=FIB)
    submit = SubmitField("Save Estimate")


class JiraForm(FlaskForm):
    server = StringField('Server URL', default="https://")
    token = PasswordField('Token')
    retroQuery = StringField('Retrospective Query')
    projQuery = StringField('Projective Query')
    cutoffDate = wtforms.DateField("History Cutoff date")
    submit = SubmitField("Import Data")
