import pytest

from test_data import estiminput_1, estiminput_2
from test_inidata import temp_filename

import estimage.data as tm
import estimage.inidata as tm_ini
import estimage.simpledata as tm_simple


def test_poll():
    pollster = tm.MemoryPollster()

    point_input = pollster.ask_points("foo")
    assert point_input.most_likely == 0

    hint = tm.EstimInput(1)

    assert not pollster.knows_points("foo")
    pollster.tell_points("foo", hint)
    assert pollster.knows_points("foo")
    point_input = pollster.ask_points("foo")

    assert point_input.most_likely == 1


def test_pollster_provides_known_data():
    pollster = tm.MemoryPollster()
    pollster.tell_points("esti", tm.EstimInput(2))
    assert pollster.provide_info_about([]) == dict()
    assert pollster.provide_info_about(["x"]) == dict()

    assert pollster.provide_info_about(["esti"]) == dict(esti=tm.EstimInput(2))
    assert pollster.provide_info_about(["x", "esti"]) == dict(esti=tm.EstimInput(2))


def test_pollster_fills_in():
    result = tm.TaskModel("esti")
    pollster = tm.MemoryPollster()
    pollster.tell_points("esti", tm.EstimInput(2))
    pollster.inform_results([result])
    assert result.point_estimate.expected == 2

    estimodel = tm.EstiModel()
    estimodel.new_element("esti")

    all_results = estimodel.get_all_task_models()
    pollster.inform_results(all_results)
    assert estimodel.point_estimate.expected == 2

    estimodel.new_element("xsti")
    pollster.tell_points("xsti", tm.EstimInput(3))

    all_results = estimodel.get_all_task_models()
    pollster.inform_results(all_results)
    assert estimodel.point_estimate.expected == 5


@pytest.fixture
def pollster_inifile(temp_filename):
    class TmpIniPollster(tm_ini.IniPollster):
        CONFIG_FILENAME = temp_filename

    yield TmpIniPollster


@pytest.fixture
def pollster_iniuser(temp_filename):
    class TmpIniPollster(tm_ini.IniPollster, tm_simple.UserPollsterBase):
        CONFIG_FILENAME = temp_filename

        def __init__(self, * args, ** kwargs):
            super().__init__(username="user", *args, ** kwargs)

    yield TmpIniPollster


@pytest.fixture
def pollster_iniauthoritative(temp_filename):
    class TmpIniPollster(tm_ini.IniPollster, tm_simple.AuthoritativePollsterBase):
        CONFIG_FILENAME = temp_filename

    yield TmpIniPollster


@pytest.fixture(params=["memory", "ini", "ini_user", "ini_authoritative"])
def pollster_class(request, pollster_inifile, pollster_iniuser, pollster_iniauthoritative):
    pollsters = dict(
        memory=tm.MemoryPollster,
        ini=pollster_inifile,
        ini_user=pollster_iniuser,
        ini_authoritative=pollster_iniauthoritative,
    )
    return pollsters[request.param]


def test_pollster_save_load(pollster_class):
    data = pollster_class()
    points = tm.EstimInput()
    points.most_likely = 1
    data.tell_points("first", points)

    data2 = pollster_class()
    points2 = data2.ask_points("first")

    assert points.most_likely == points2.most_likely


@pytest.fixture(params=["memory", "ini"])
def ns_pollster(request, pollster_inifile):
    pollsters = dict(
        memory=tm.MemoryPollster(),
        ini=pollster_inifile(),
    )
    return pollsters[request.param]


def test_pollster_forgets(ns_pollster, estiminput_1):
    name = ""
    assert not ns_pollster.knows_points(name)
    ns_pollster.tell_points(name, estiminput_1)
    assert ns_pollster.knows_points(name)
    ns_pollster.forget_points(name)
    assert not ns_pollster.knows_points(name)
    assert ns_pollster.ask_points(name) == tm.EstimInput()


def test_pollster_with_namespaces(ns_pollster, estiminput_1, estiminput_2):
    ns_pollster.set_namespace("")
    point_name = "one"
    ns_pollster.tell_points(point_name, estiminput_1)
    ns_pollster.set_namespace("x")

    assert not ns_pollster.knows_points(point_name)
    assert ns_pollster.ask_points(point_name) == tm.EstimInput(0)
    ns_pollster.tell_points(point_name, estiminput_2)
    assert ns_pollster.knows_points(point_name)
    assert ns_pollster.ask_points(point_name) == estiminput_2

    ns_pollster.set_namespace("")

    assert ns_pollster.knows_points(point_name)
    assert ns_pollster.ask_points(point_name) == estiminput_1


def test_integrate():
    pollster = tm.MemoryPollster()
    est = tm.EstiModel()

    name1 = "foo"
    e1 = tm.TaskModel(name1)
    est.add_element(e1)

    pollster.tell_points(name1, tm.EstimInput(3))
    user_point_input = pollster.ask_points(name1)
    est.estimate_points_of(name1, user_point_input)

    name2 = "bar"
    e2 = tm.TaskModel(name2)
    est.add_element(e2)

    pollster.tell_points(name2, tm.EstimInput(5))
    user_point_input = pollster.ask_points(name2)

    est.estimate_points_of(name2, user_point_input)

    assert e1.point_estimate.expected == 3
    assert e1.point_estimate.variance == 0
    assert e2.point_estimate.expected == 5

    assert est.main_composition.point_estimate.expected == 8
    assert est.main_composition.point_estimate.variance == 0
