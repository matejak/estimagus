import estimage.plugins.expected as tm

from estimage import data


def test_sanity():
    simple = tm.ExpectingCard("something")
    assert simple.get_expected_volume() == 0
    simple.point_cost = 5
    assert simple.get_expected_volume() == 0


def test_child():
    # TODO: Will need a model
    simple = tm.ExpectingCard("something")
    simple.point_cost = 5
    child = tm.ExpectingCard("work")
    child.point_cost = 2
    simple.add_element(child)
    assert simple.get_expected_volume() == 3
