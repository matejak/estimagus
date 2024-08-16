import wtforms

from ...plugins.base.forms import BaseForm


class WSJFForm(BaseForm):
    business_value = wtforms.DecimalField("Business Value")
    risk_opportunity = wtforms.DecimalField("Risk Reduction / Opportunity Enablement")
    time_sensitivity = wtforms.DecimalField("Time Sensitivity")
    task_name = wtforms.HiddenField('task_name')
    submit = wtforms.SubmitField("Update Priority")
