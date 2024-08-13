import pytest

from estimage import plugins, PluginResolver
import estimage.plugins.wsjf as tm

from tests.test_card import base_card_load_save, fill_card_instance_with_stuff, assert_cards_are_equal, TesCardIO
from tests.test_inidata import temp_filename, inifile_temploc, cardio_inifile_cls


@pytest.fixture()
def wsjf_cls():
    resolver = PluginResolver()
    resolver.add_known_extendable_classes()
    assert "BaseCard" in resolver.class_dict
    resolver.resolve_extension(tm, dict(BaseCard="WSJFCard"))
    cls = resolver.class_dict["BaseCard"]
    return cls


@pytest.fixture()
def wsjf_card(wsjf_cls):
    return wsjf_cls("card")


@pytest.fixture(params=("ini",))
def card_io(request, cardio_inifile_cls):
    generator = TesCardIO(tm.WSJFCard, ini_base=cardio_inifile_cls)
    backend = request.param
    return generator(backend)


def test_cod(wsjf_card):
    assert wsjf_card.cost_of_delay == 0

    wsjf_card.business_value = 2
    wsjf_card.risk_and_opportunity = 1
    assert wsjf_card.cost_of_delay == 3


def test_cod_with_dependencies(wsjf_card):
    wsjf_fill(wsjf_card)
    sum_of_own_fields = 15
    assert wsjf_card.cost_of_delay >= sum_of_own_fields
    wsjf_card.point_cost = 1
    assert wsjf_card.cost_of_delay == sum_of_own_fields + 2
    wsjf_card.point_cost = 2
    assert wsjf_card.cost_of_delay == sum_of_own_fields + 2 * 2


def test_priority(wsjf_card):
    assert wsjf_card.wsjf_score == 0
    wsjf_fill(wsjf_card)
    with pytest.raises(ValueError, match="size"):
        wsjf_card.wsjf_score
    wsjf_card.point_cost = 1
    sum_of_own_fields = 15
    assert wsjf_card.cost_of_delay == sum_of_own_fields + 2
    wsjf_card.point_cost = 2
    assert wsjf_card.wsjf_score == sum_of_own_fields / 2 + 2


def test_persistence(card_io, wsjf_cls):
    base_card_load_save(card_io, wsjf_cls, plugin_fill, plugin_test)


def test_load_default(card_io, wsjf_cls):
    one = wsjf_cls.load_metadata("one", card_io)


def wsjf_fill(card):
    card.business_value = 7
    card.risk_and_opportunity = 3
    card.time_sensitivity = 5
    card.inherited_priority["one"] = 2


def plugin_fill(card):
    fill_card_instance_with_stuff(card)
    wsjf_fill(card)


def plugin_test(lhs, rhs):
    assert_cards_are_equal(lhs, rhs)
    assert lhs.business_value == rhs.business_value
    assert lhs.risk_and_opportunity == rhs.risk_and_opportunity
    assert lhs.cost_of_delay == rhs.cost_of_delay
    assert lhs.time_sensitivity == rhs.time_sensitivity
    assert lhs.inherited_priority["one"] == rhs.inherited_priority["one"]
