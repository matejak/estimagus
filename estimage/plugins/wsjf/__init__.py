from ... import persistence
from . import forms


TEMPLATE_OVERRIDES = {
    "issue_view.html": "prio_issue_fields.html",
}

EXPORTS = {
    "BaseCard": "WSJFCard",
    "ProjectiveForms": "ProjectiveForms",
}


class ProjectiveForms:
    def add_sections(self):
        super().add_sections()
        self._add_section(20, name="wsjf", title="Prioritization")

    def instantiate_forms(self, app):
        super().instantiate_forms(app)
        form = forms.WSJFForm()
        self.forms["wsjf"] = form

    def setup_forms_according_to_context(self, context, card):
        super().setup_forms_according_to_context(context, card)
        self.forms["wsjf"].business_value.data = card.business_value
        self.forms["wsjf"].time_sensitivity.data = card.time_sensitivity
        self.forms["wsjf"].risk_and_opportunity.data = card.risk_and_opportunity


class WSJFCard:
    business_value: float = 0
    risk_and_opportunity: float = 0
    time_sensitivity: float = 0

    def _get_inherent_cost_of_delay(self):
        return (
            self.business_value
            + self.risk_and_opportunity
            + self.time_sensitivity)

    @property
    def cost_of_delay(self):
        ret = self._get_inherent_cost_of_delay()
        ret += sum(self.inherited_priority.values()) * self.point_cost
        return ret

    @property
    def intrinsic_cost_of_delay(self):
        return self.business_value + self.risk_and_opportunity + self.time_sensitivity

    @property
    def inherited_priority(self):
        ret = self._shallow_inherited_priority()
        for c in self.get_direct_dependencies():
            new_prio = c.inherited_priority
            ret.update(new_prio)
        return ret

    def _shallow_inherited_priority(self):
        ret = dict()
        for c in self.get_direct_dependencies():
            prio = c.intrinsic_cost_of_delay / c.point_cost
            if not prio:
                continue
            ret[c.name] = prio
        return ret

    @property
    def wsjf_score(self):
        if self.cost_of_delay == 0:
            return 0
        if self.point_cost == 0:
            msg = f"Point Cost aka size of '{self.name}' is unknown, as is its priority."
            raise ValueError(msg)
        return self.cost_of_delay / self.point_cost

    def pass_data_to_saver(self, saver):
        super().pass_data_to_saver(saver)
        saver.save_wsjf_fields(self)

    def load_data_by_loader(self, loader):
        super().load_data_by_loader(loader)
        loader.load_wsjf_fields(self)


@persistence.multiloader_of(WSJFCard, ("ini", "toml", "memory"))
class IniCardStateLoader:
    def load_wsjf_fields(self, card):
        card.business_value = float(self._get_our(card, "wsjf_business_value", 0))
        card.risk_and_opportunity = float(self._get_our(card, "wsjf_risk_and_opportunity", 0))
        card.time_sensitivity = float(self._get_our(card, "time_sensitivity", 0))


@persistence.multisaver_of(WSJFCard, ("ini", "toml", "memory"))
class IniCardStateSaver:
    def save_wsjf_fields(self, card):
        self._store_our(card, "wsjf_business_value", str(card.business_value))
        self._store_our(card, "wsjf_risk_and_opportunity", str(card.risk_and_opportunity))
        self._store_our(card, "time_sensitivity", str(card.time_sensitivity))
