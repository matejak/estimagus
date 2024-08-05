from ... import persistence


class WSJFCard:
    business_value: float = 0
    risk_and_opportunity: float = 0

    @property
    def cost_of_delay(self):
        return self.business_value + self.risk_and_opportunity

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


@persistence.saver_of(WSJFCard, "ini")
class IniCardStateSaver:
    def save_wsjf_fields(self, card):
        self._store_our(card, "wsjf_business_value", str(card.business_value))
        self._store_our(card, "wsjf_risk_and_opportunity", str(card.risk_and_opportunity))
