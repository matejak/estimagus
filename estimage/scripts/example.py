from estimage import data


AUTHORITATIVE_STORAGE = dict(
    one=2,
    two=4,
    three=6,
)


OUR_INPUT = dict(
    one=[1, 2, 3],
    two=[3, 4, 6],
    three=[5, 6, 10],
)


class MemoryCard(data.BaseCard):
    def __init__(self, name):
        self.name = name

    def load(self):
        return self.load_point_cost()

    def _load_point_cost(self):
        return str(AUTHORITATIVE_STORAGE[self.name])

    def _save_point_cost(self, cost_str):
        global AUTHORITATIVE_STORAGE
        AUTHORITATIVE_STORAGE[self.name] = float(cost_str)


class MemoryPollster(data.Pollster):
    def ask_points(self, name):
        triple = OUR_INPUT[name]
        result = data.EstimInput(triple[1])
        result.optimistic = triple[0]
        result.pessimistic = triple[2]
        return result

    def tell_points(self, name, points):
        OUR_INPUT[name] = [points.optimistic, points.most_likely, points.pessimistic]


class SimpleModel(data.EstiModel):
    def __init__(self, card_list):
        super().__init__()
        for t in card_list:
            self.new_element(t.name)


def demo():
    names = AUTHORITATIVE_STORAGE.keys()

    cards = {name: MemoryCard(name) for name in names}
    for name, t in cards.items():
        t.load()

    # view cards
    # estimate them
    pollster = MemoryPollster()

    estimator = SimpleModel(cards.values())

    for name in names:
        estimate = pollster.ask_points(name)
        estimator.estimate_points_of(name, estimate)
        expected = estimator.point_estimate_of(name).expected
        print(f"{name}: Most likely: {estimate.most_likely}, expected: {expected}")
        cards[name].save_point_cost()

    for name, t in cards.items():
        t.load()
        print(f"{name}: {t.point_cost=}")


if __name__ == "__main__":
    demo()
