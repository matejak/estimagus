from ... import persistence


TEMPLATE_OVERRIDES = {
    "issue_view.html": "prio_issue_fields.html",
}

EXPORTS = {
    "BaseCard": "WSJFCard",
}


class WSJFCard:
    business_value: float = 0
    risk_and_opportunity: float = 0
    time_sensitivity: float = 0
    inherited_priority: dict

    def __init__(self, * args, **kwargs):
        super().__init__(* args, ** kwargs)
        self.inherited_priority = dict()

    @property
    def cost_of_delay(self):
        ret = (
            self.business_value
            + self.risk_and_opportunity
            + self.time_sensitivity)
        ret += sum(self.inherited_priority.values()) * self.point_cost
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


@persistence.loader_of(WSJFCard, "ini")
class IniCardStateLoader:
    def load_wsjf_fields(self, card):
        card.business_value = float(self._get_our(card, "wsjf_business_value"))
        card.risk_and_opportunity = float(self._get_our(card, "wsjf_risk_and_opportunity"))
        card.time_sensitivity = float(self._get_our(card, "time_sensitivity"))

        records = self._get_our(card, "inherited_priority")
        for record in records.split(";"):
            source, value = record.split(",")
            card.inherited_priority[source] = float(value)


@persistence.saver_of(WSJFCard, "ini")
class IniCardStateSaver:
    def save_wsjf_fields(self, card):
        self._store_our(card, "wsjf_business_value", str(card.business_value))
        self._store_our(card, "wsjf_risk_and_opportunity", str(card.risk_and_opportunity))
        self._store_our(card, "time_sensitivity", str(card.time_sensitivity))

        record = []
        for source, value in card.inherited_priority.items():
            record.append(f"{source},{value}")
        self._store_our(card, "inherited_priority", ";".join(record))
