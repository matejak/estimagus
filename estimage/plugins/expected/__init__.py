from ...data import BaseCard


class ExpectingCard(BaseCard):
    def get_expected_volume(self):
        return 0
