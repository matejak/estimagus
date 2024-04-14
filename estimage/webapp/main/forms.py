import wtforms
from wtforms import StringField, BooleanField, SubmitField, ValidationError

from ... import PluginResolver
from ...plugins.base.forms import BaseForm


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


class PromotionMixin(BaseForm):
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


@PluginResolver.class_is_extendable("AuthoritativeForm")
class AuthoritativeForm(PromotionMixin, SubmitMixin):
    def __init__(self, * args, ** kwargs):
        id_prefix = "authoritative_"
        super().__init__(* args, id_prefix=id_prefix, ** kwargs)

    def clear_to_go(self):
        pass

    def get_point_cost(self):
        return float(self.point_cost.data)

    task_name = wtforms.HiddenField('task_name')
    point_cost = wtforms.HiddenField('point_cost')
    i_kid_you_not = BooleanField("Consensus should be published to the tracker")
    submit = SubmitField("Publish Consensus Estimate")


FIB = [0, 1, 2, 3, 5, 8, 13, 21, 34]


class NumberEstimationForm(BaseForm, SubmitMixin, DeleteMixin):
    optimistic = wtforms.DecimalField("Optimistic")
    most_likely = wtforms.DecimalField("Most Likely")
    pessimistic = wtforms.DecimalField("Pessimistic")
    submit = SubmitField("Save Estimate")
    delete = SubmitField("Forget Estimate")

    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.disable_delete_button()

    def validate_optimistic(self, field):
        if field.data and field.data > self.most_likely.data:
            msg = "The optimistic value mustn't exceed the most likely value"
            raise ValidationError(msg)

    def validate_pessimistic(self, field):
        if field.data and field.data < self.most_likely.data:
            msg = "The pessimistic value mustn't go below the most likely value"
            raise ValidationError(msg)

    def get_all_errors(self):
        all_errors = set()
        for field_errors in self.errors.values():
            all_errors.update(set(field_errors))
        return all_errors


class PointEstimationForm(BaseForm):
    optimistic = wtforms.SelectField("Optimistic", choices=FIB)
    most_likely = wtforms.SelectField("Most Likely", choices=FIB)
    pessimistic = wtforms.SelectField("Pessimistic", choices=FIB)
    submit = SubmitField("Save Estimate")


class MultiCheckboxField(wtforms.SelectMultipleField):
    """
    A multiple-select, except displays a list of checkboxes.

    Iterating the field will produce subfields, allowing custom rendering of
    the enclosed checkbox fields.
    """
    widget = wtforms.widgets.ListWidget(prefix_label=False)
    option_widget = wtforms.widgets.CheckboxInput()


@PluginResolver.class_is_extendable("ProblemForm")
class ProblemForm(BaseForm):
    def __init__(self, ** kwargs):
        self.extending_fields = []
        super().__init__(** kwargs)

    def add_problems(self, all_problems):
        for p in all_problems:
            self.problems.choices.append((p.affected_card_name, ""))

    def add_problems_and_cat(self, problems_category, problems):
        for p in problems:
            self.problems.choices.append((p.affected_card_name, p))

        self.problem_category.data = problems_category.name
        if s := problems_category.solution:
            self.solution.data = s.description

    problem_category = wtforms.HiddenField("problem_cat")
    problems = MultiCheckboxField("Problems", choices=[])
    solution = wtforms.StringField("Solution", render_kw={'readonly': True})
    submit = SubmitField("Solve Selected Problems")
