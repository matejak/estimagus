import datetime

import pytest
import numpy as np
import numpy.testing

from estimage import history, data
import estimage.history.aggregation as tm
import estimage.entities.target as target

from test_events import early_event, ONE_DAY, PERIOD_START, LONG_PERIOD_END
from test_history_progress import simple_target, repre, oneday_repre, twoday_repre, twoday_repre_done_in_day


@pytest.fixture
def supertask_target(simple_target):
    ret = target.BaseTarget("supertask")
    ret.add_element(simple_target)
    return ret


@pytest.fixture
def another_supertask_target(simple_target):
    ret = target.BaseTarget("another-supertask")
    subtask = simple_target
    subtask.name = "subtask"
    ret.add_element(subtask)
    return ret


def test_aggregation(repre):
    someday = datetime.datetime(2022, 10, 10)
    day_after = someday + ONE_DAY

    repre.update(day_after, points=6, status=target.State.review)

    aggregation = tm.Aggregation()
    aggregation.add_repre(repre)
    aggregation.add_repre(repre)

    assert aggregation.states_on(someday) == {repre.get_status_at(someday)}
    assert aggregation.states_on(someday) != {repre.get_status_at(day_after)}

    assert aggregation.points_on(someday) == 2 * repre.get_points_at(someday)
    assert aggregation.points_on(day_after) == 2 * repre.get_points_at(day_after)


def test_aggregation_no_time_bounds():
    aggregation = tm.Aggregation()
    assert aggregation.start is None
    assert aggregation.end is None


def test_aggregation_get_time_bounds(repre):
    aggregation = tm.Aggregation()
    aggregation.add_repre(repre)

    assert aggregation.start == repre.start
    assert aggregation.end == repre.end


def test_aggregation_enforce_time_bounds(repre, oneday_repre):
    aggregation = tm.Aggregation()
    aggregation.add_repre(repre)
    aggregation.add_repre(repre)
    with pytest.raises(ValueError):
        aggregation.add_repre(oneday_repre)


def check_repre_against_target(target, repre, start, end):
    assert repre.start == start
    assert repre.end == end
    assert repre.task_name == target.name
    assert repre.get_points_at(start) == target.point_cost
    assert repre.get_status_at(start) == target.state


def test_simple_target_to_aggregation(simple_target):
    start = PERIOD_START
    end = PERIOD_START

    aggregation = tm.Aggregation.from_target(simple_target, start, end)
    assert len(aggregation.repres) == 1
    repre = aggregation.repres[0]

    check_repre_against_target(simple_target, repre, start, end)


def test_simple_target_to_aggregation_long(simple_target):
    start = PERIOD_START
    end = LONG_PERIOD_END

    aggregation = tm.Aggregation.from_target(simple_target, start, end)
    assert len(aggregation.repres) == 1
    repre = aggregation.repres[0]

    check_repre_against_target(simple_target, repre, start, end)


def test_supertask_to_aggregation_long(supertask_target):
    start = PERIOD_START
    end = LONG_PERIOD_END

    aggregation = tm.Aggregation.from_target(supertask_target, start, end)
    assert len(aggregation.repres) == 1
    repre = aggregation.repres[0]

    check_repre_against_target(supertask_target.dependents[0], repre, start, end)


def test_supertask_with_more_subtasks_to_aggregation_long(supertask_target):
    start = PERIOD_START
    end = LONG_PERIOD_END

    next_subtask = target.BaseTarget("next_subtask")
    supertask_target.add_element(next_subtask)

    aggregation = tm.Aggregation.from_target(supertask_target, start, end)
    assert len(aggregation.repres) == 2

    check_repre_against_target(supertask_target.dependents[0], aggregation.repres[0], start, end)
    check_repre_against_target(supertask_target.dependents[1], aggregation.repres[1], start, end)


def test_supertasks_to_aggregation_long(supertask_target, another_supertask_target):
    start = PERIOD_START
    end = LONG_PERIOD_END

    aggregation = tm.Aggregation.from_targets(
        [supertask_target, another_supertask_target], start, end)
    assert len(aggregation.repres) == 2

    check_repre_against_target(supertask_target.dependents[0], aggregation.repres[0], start, end)
    check_repre_against_target(another_supertask_target.dependents[0], aggregation.repres[1], start, end)


def test_aggregation_point_velocity_array(twoday_repre_done_in_day):
    a = tm.Aggregation()
    assert len(a.get_velocity_array()) == 0

    a.add_repre(twoday_repre_done_in_day)
    assert np.all(a.get_velocity_array() == twoday_repre_done_in_day.get_velocity_array())


def test_aggregation_plan(twoday_repre_done_in_day):
    a = tm.Aggregation()

    a.add_repre(twoday_repre_done_in_day)
    points = twoday_repre_done_in_day.get_points_at(PERIOD_START)

    another_points = 8
    another_repre = history.Progress(a.start, a.end)
    another_repre.status_timeline.set_value_at(a.start, target.State.todo)
    another_repre.points_timeline.set_value_at(PERIOD_START, another_points)
    a.add_repre(another_repre)

    plan = a.get_plan_array()
    assert plan[0] == points + another_points
    assert plan[-1] == 0


def test_aggregation_point_velocity_trivial(twoday_repre_done_in_day):
    a = tm.Aggregation()
    assert a.point_velocity.expected == 0

    a.add_repre(twoday_repre_done_in_day)
    assert a.point_velocity.expected == 1
    assert a.point_velocity.sigma == pytest.approx(1)


def test_target_span_propagates_to_children():
    END = PERIOD_START + 5 * ONE_DAY
    parent = target.BaseTarget("p")
    parent.work_span = (PERIOD_START + ONE_DAY, END)
    child = target.BaseTarget("c")
    parent.add_element(child)

    r = tm.convert_target_to_representations_of_leaves(parent, PERIOD_START, END)[0]
    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 1

    parent.work_span = (None, END - ONE_DAY)
    r = tm.convert_target_to_representations_of_leaves(parent, PERIOD_START, END)[0]
    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 0.75
    assert r.remainder_timeline.value_at(END - ONE_DAY) == 0

    parent.work_span = (PERIOD_START + ONE_DAY, None)
    r = tm.convert_target_to_representations_of_leaves(parent, PERIOD_START, END)[0]
    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 1.0
    assert r.remainder_timeline.value_at(END) == 0


def test_target_span_incomplete_works():
    END = PERIOD_START + 5 * ONE_DAY
    t = target.BaseTarget("")
    t.work_span = (None, END - ONE_DAY)
    r = tm.convert_target_to_representations_of_leaves(t, PERIOD_START, END)[0]
    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 0.75
    assert r.remainder_timeline.value_at(END - ONE_DAY) == 0

    t.work_span = (None, PERIOD_START - ONE_DAY)
    r = tm.convert_target_to_representations_of_leaves(t, PERIOD_START, END)[0]

    t.work_span = (END + ONE_DAY, END + ONE_DAY)
    r = tm.convert_target_to_representations_of_leaves(t, PERIOD_START, END)[0]
    assert r.remainder_timeline.value_at(PERIOD_START) == 1
    assert r.remainder_timeline.value_at(END - ONE_DAY) == 1
    assert r.remainder_timeline.value_at(END) == 1

    t.work_span = (PERIOD_START - 5 * ONE_DAY, END + 5 * ONE_DAY)
    r = tm.convert_target_to_representations_of_leaves(t, PERIOD_START, END)[0]
    assert r.remainder_timeline.value_at(PERIOD_START) == pytest.approx(2 / 3)
    assert r.remainder_timeline.value_at(END) == pytest.approx(1 / 3)


def test_target_span_not_started_works():
    END = PERIOD_START + 5 * ONE_DAY
    t = target.BaseTarget("")

    t.work_span = (PERIOD_START - ONE_DAY, PERIOD_START - ONE_DAY)
    r = tm.convert_target_to_representations_of_leaves(t, PERIOD_START, END)[0]
    assert r.remainder_timeline.value_at(END) == 0
    assert r.remainder_timeline.value_at(PERIOD_START) == 0

    t.work_span = (PERIOD_START - ONE_DAY, PERIOD_START + ONE_DAY)
    r = tm.convert_target_to_representations_of_leaves(t, PERIOD_START, END)[0]
    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 0
    assert r.remainder_timeline.value_at(PERIOD_START) == 0.5


def test_target_span_propagates():
    END = PERIOD_START + 5 * ONE_DAY
    t = target.BaseTarget("")
    r = tm.convert_target_to_representations_of_leaves(t, PERIOD_START, END)[0]

    assert r.remainder_timeline.value_at(PERIOD_START) == 1
    assert r.remainder_timeline.value_at(END) == 0

    t.work_span = (PERIOD_START + 2 * ONE_DAY, END - ONE_DAY)
    r = tm.convert_target_to_representations_of_leaves(t, PERIOD_START, END)[0]

    assert r.remainder_timeline.value_at(PERIOD_START) == 1
    assert r.remainder_timeline.value_at(END) == 0

    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 1
    assert r.remainder_timeline.value_at(END - ONE_DAY) == 0

    assert r.remainder_timeline.value_at(PERIOD_START + 2 * ONE_DAY) == 1
    assert r.remainder_timeline.value_at(PERIOD_START + 3 * ONE_DAY) == 0.5


def test_target_span_starting_before_is_correctly_recalculated():
    END = PERIOD_START + 5 * ONE_DAY
    t = target.BaseTarget("")
    t.work_span = (PERIOD_START - ONE_DAY, END - ONE_DAY)
    r = tm.convert_target_to_representations_of_leaves(t, PERIOD_START, END)[0]
    assert r.remainder_timeline.value_at(PERIOD_START) == 0.8


def test_target_span_ending_after_is_recalculated():
    END = PERIOD_START + 5 * ONE_DAY
    t = target.BaseTarget("")
    t.work_span = (PERIOD_START + ONE_DAY, END + ONE_DAY)
    r = tm.convert_target_to_representations_of_leaves(t, PERIOD_START, END)[0]
    overflowing_ratio = ONE_DAY / (t.work_span[1] - t.work_span[0])
    assert r.remainder_timeline.value_at(END) == pytest.approx(overflowing_ratio)


@pytest.fixture
def simple_long_period_aggregation(simple_target):
    start = PERIOD_START
    end = LONG_PERIOD_END
    ret = tm.Aggregation.from_target(simple_target, start, end)
    return ret


def test_event_processing(simple_long_period_aggregation):
    start = PERIOD_START

    evt_bad = data.Event("another task", "points", start + ONE_DAY)
    evt_bad.value_after = "3"
    evt_bad.value_before = "3"

    simple_long_period_aggregation.process_events([evt_bad])

    repre = simple_long_period_aggregation.repres[0]
    assert repre.get_points_at(start) == 8

    evt_good = data.Event("task", "points", start + ONE_DAY)
    evt_good.value_after = "5"
    evt_good.value_before = "1"

    simple_long_period_aggregation.process_events([evt_bad, evt_good])

    repre = simple_long_period_aggregation.repres[0]
    assert repre.get_points_at(start) == 1


def test_aggregation_and_event_manager(simple_long_period_aggregation, simple_target, early_event):
    mgr = data.EventManager()
    early_event.quantity = "points"
    simple_long_period_aggregation.process_event_manager(mgr)
    repre = simple_long_period_aggregation.repres[0]
    assert repre.get_points_at(PERIOD_START) == repre.get_points_at(LONG_PERIOD_END)
    assert repre.get_points_at(PERIOD_START) == simple_target.point_cost

    early_event.task_name = simple_target.name + "---"
    mgr.add_event(early_event)
    simple_long_period_aggregation.process_event_manager(mgr)
    repre = simple_long_period_aggregation.repres[0]
    assert repre.get_points_at(PERIOD_START) == repre.get_points_at(LONG_PERIOD_END)
    assert repre.get_points_at(PERIOD_START) == simple_target.point_cost

    early_event.task_name = simple_target.name
    early_event.value_after = "99"
    mgr.add_event(early_event)
    simple_long_period_aggregation.process_event_manager(mgr)
    repre = simple_long_period_aggregation.repres[0]
    assert repre.get_points_at(LONG_PERIOD_END) == float(early_event.value_after)
    assert repre.get_points_at(PERIOD_START) == float(early_event.value_before)
