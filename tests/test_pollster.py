import pytest

from test_data import estiminput_1, estiminput_2
from test_inidata import temp_filename

import estimage.data as tm
from estimage.persistence.pollster import ini, memory
import estimage.simpledata as tm_simple


@pytest.fixture
def pollster_inifile_cls(temp_filename):
    class TmpIniPollsterIO(ini.IniPollsterIO):
        CONFIG_FILENAME = temp_filename

    yield TmpIniPollsterIO


@pytest.fixture(params=("ini", "memory"))
def relevant_io(pollster_inifile_cls, request):
    choices = dict(
        ini=pollster_inifile_cls,
        memory=memory.MemoryPollsterIO,
    )
    return choices[request.param]


def test_poll(relevant_io):
    pollster = tm.Pollster(relevant_io)

    point_input = pollster.ask_points("foo")
    assert point_input.most_likely == 0

    hint = tm.EstimInput(1)

    assert not pollster.knows_points("foo")
    pollster.tell_points("foo", hint)
    assert pollster.knows_points("foo")
    point_input = pollster.ask_points("foo")

    assert point_input.most_likely == 1


def test_pollster_provides_known_data(relevant_io):
    pollster = tm.Pollster(relevant_io)
    pollster.tell_points("esti", tm.EstimInput(2))
    assert pollster.provide_info_about([]) == dict()
    assert pollster.provide_info_about(["x"]) == dict()

    assert pollster.provide_info_about(["esti"]) == dict(esti=tm.EstimInput(2))
    assert pollster.provide_info_about(["x", "esti"]) == dict(esti=tm.EstimInput(2))


def test_pollster_fills_in(relevant_io):
    result = tm.TaskModel("esti")
    pollster = tm.Pollster(relevant_io)
    pollster.tell_points("esti", tm.EstimInput(2))
    pollster.supply_valid_estimations_to_tasks([result])
    assert result.nominal_point_estimate.expected == 2

    estimodel = tm.EstiModel()
    estimodel.new_element("esti")

    all_results = estimodel.get_all_task_models()
    pollster.supply_valid_estimations_to_tasks(all_results)
    assert estimodel.nominal_point_estimate.expected == 2

    estimodel.new_element("xsti")
    pollster.tell_points("xsti", tm.EstimInput(3))

    all_results = estimodel.get_all_task_models()
    pollster.supply_valid_estimations_to_tasks(all_results)
    assert estimodel.nominal_point_estimate.expected == 5

    defective_input = tm.EstimInput(3)
    defective_input.pessimistic = 2

    pollster.tell_points("esti", defective_input)
    with pytest.raises(ValueError, match="esti"):
        pollster.supply_valid_estimations_to_tasks([result])


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


def test_pollster_save_load(relevant_io):
    pollster = tm.Pollster(relevant_io)
    points = tm.EstimInput()
    points.most_likely = 1
    pollster.tell_points("first", points)

    pollster2 = tm.Pollster(relevant_io)
    points2 = pollster2.ask_points("first")

    assert points.most_likely == points2.most_likely


def test_pollster_forgets(relevant_io, estiminput_1):
    name = ""
    pollster = tm.Pollster(relevant_io)
    assert not pollster.knows_points(name)
    pollster.tell_points(name, estiminput_1)
    assert pollster.knows_points(name)
    pollster.forget_points(name)
    assert not pollster.knows_points(name)
    assert pollster.ask_points(name) == tm.EstimInput()


def test_pollster_with_namespaces(relevant_io, estiminput_1, estiminput_2):
    ns_pollster = tm.Pollster(relevant_io)
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


def test_integrate(relevant_io):
    pollster = tm.Pollster(relevant_io)
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

    assert e1.nominal_point_estimate.expected == 3
    assert e1.nominal_point_estimate.variance == 0
    assert e2.nominal_point_estimate.expected == 5

    assert est.main_composition.nominal_point_estimate.expected == 8
    assert est.main_composition.nominal_point_estimate.variance == 0
