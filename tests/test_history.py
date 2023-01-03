import datetime

import pytest
import numpy as np

import estimage.history as tm
import estimage.entities.target as target
import estimage.data as data

from test_events import early_event, less_early_event, late_event, ONE_DAY, PERIOD_START, LONG_PERIOD_END


@pytest.mark.dependency()
def test_timeline_length():
    start = PERIOD_START
    end = LONG_PERIOD_END
    timeline = tm.Timeline(start, end)
    assert timeline.days == 21


@pytest.mark.dependency(depends=["test_timeline_length"])
def test_timeline_masking():
    timeline = tm.Timeline(PERIOD_START, LONG_PERIOD_END)
    timeline.set_value_at(PERIOD_START + ONE_DAY, 55)
    mask = timeline.get_value_mask(55)
    assert sum(mask) == 1
    assert timeline.get_masked_values(mask)[0] == 55


@pytest.fixture
def long_timeline():
    return tm.Timeline(PERIOD_START, LONG_PERIOD_END)


def test_localize_events(early_event, less_early_event, late_event):
    early_loc = tm.localize_date(PERIOD_START, early_event.time)
    less_early_loc = tm.localize_date(PERIOD_START, less_early_event.time)

    assert int(early_loc) == early_loc
    assert int(less_early_loc) == less_early_loc

    assert early_loc <= less_early_loc
    assert early_loc < tm.localize_date(PERIOD_START, late_event.time)

    assert tm.localize_date(PERIOD_START, PERIOD_START) == 0


def test_beyond_timeline(long_timeline):
    time_too_late = datetime.datetime(2023, 1, 1)
    with pytest.raises(ValueError):
        long_timeline.process_events([data.Event("", None, time_too_late)])

    time_too_early = datetime.datetime(2021, 1, 1)
    with pytest.raises(ValueError):
        long_timeline.process_events([data.Event("", None, time_too_early)])


def test_timeline_applies_distinct_events(long_timeline, early_event, late_event):
    long_timeline.process_events([early_event, late_event])
    assert long_timeline.value_at(LONG_PERIOD_END) == 0
    assert long_timeline.value_at(PERIOD_START) == 15
    assert long_timeline.value_at(early_event.time + ONE_DAY * 2) == 10
    assert long_timeline.value_at(late_event.time) == 10
    assert long_timeline.value_at(late_event.time + ONE_DAY) == 0


def test_reset_timeline(long_timeline):
    long_timeline.recreate_with_value(3, dtype=int)
    assert long_timeline.value_at(PERIOD_START) == long_timeline.value_at(LONG_PERIOD_END)
    assert long_timeline.value_at(PERIOD_START) == 3


def test_timeline_process_close_and_distinct_events(
        long_timeline, early_event, less_early_event, late_event):

    long_timeline.process_events([less_early_event, early_event, late_event])

    assert long_timeline.value_at(LONG_PERIOD_END) == 0
    assert long_timeline.value_at(PERIOD_START) == 15
    assert long_timeline.value_at(early_event.time + ONE_DAY * 2) == 10
    assert long_timeline.value_at(late_event.time) == 10
    assert long_timeline.value_at(late_event.time + ONE_DAY) == 0
    assert long_timeline.value_at(less_early_event.time) == 17


@pytest.fixture
def repre():
    start = PERIOD_START
    end = LONG_PERIOD_END

    representation = tm.Repre(start, end)
    return representation


@pytest.fixture
def oneday_repre():
    start = PERIOD_START
    end = PERIOD_START

    representation = tm.Repre(start, end)
    return representation


@pytest.fixture
def twoday_repre():
    start = PERIOD_START
    end = PERIOD_START + ONE_DAY

    representation = tm.Repre(start, end)
    return representation


def test_repre(repre):
    someday = datetime.datetime(2022, 10, 10)
    day_after = someday + ONE_DAY

    repre.update(someday, points=5, status=target.State.in_progress)

    assert repre.get_points_at(someday) == 5
    assert repre.get_status_at(someday) == target.State.in_progress

    assert repre.get_points_at(someday - ONE_DAY) == 0
    assert repre.get_status_at(someday + ONE_DAY) == target.State.unknown
    assert repre.get_status_at(someday - ONE_DAY) == target.State.unknown

    repre.fill_history_from(someday)

    assert repre.get_points_at(someday - ONE_DAY) == 5
    assert repre.get_status_at(someday - ONE_DAY) == target.State.in_progress

    repre.update(day_after, points=6, status=target.State.review)

    assert repre.get_points_at(someday) == 5
    assert repre.get_status_at(someday) == target.State.in_progress
    assert repre.get_points_at(day_after) == 6
    assert repre.get_status_at(day_after) == target.State.review

    assert sum(repre.status_is(target.State.review)) == 1
    assert repre.points_of_status(target.State.review).max() == 6

    assert sum(repre.status_is(target.State.in_progress)) == 10
    assert repre.points_of_status(target.State.in_progress).max() == 5


def test_last_measurement_events(repre):
    someday = datetime.datetime(2022, 10, 10)
    day_after = someday + ONE_DAY
    day_before = someday - ONE_DAY

    assert repre.get_points_at(someday) == 0
    assert repre.get_status_at(someday) == target.State.unknown
    assert repre.get_points_at(day_after) == 0
    assert repre.get_status_at(day_after) == target.State.unknown

    last_measurement_points = data.Event.last_points_measurement("task_name", someday, 5)
    repre.process_events(dict(points=[last_measurement_points]))

    assert repre.get_points_at(day_before) == 5
    assert repre.get_points_at(someday) == 5
    assert repre.get_points_at(day_after) == 5

    last_measurement_state = data.Event.last_state_measurement("task_name", someday, target.State.todo)
    repre.process_events(dict(state=[last_measurement_state]))
    assert repre.get_status_at(day_before) == target.State.todo
    assert repre.get_status_at(someday) == target.State.todo
    assert repre.get_status_at(day_after) == target.State.unknown


def test_out_of_bounds_events_ignored(repre):
    too_early = PERIOD_START - ONE_DAY
    too_late = LONG_PERIOD_END + ONE_DAY

    event = data.Event("", "points", too_early)
    repre.process_events(dict(points=[event]))

    event = data.Event("", "points", too_late)
    repre.process_events(dict(points=[event]))


def test_out_of_bounds_events_ok(repre):
    event = data.Event("", "points", PERIOD_START)
    repre.process_events(dict(points=[event]))

    event = data.Event("", "points", LONG_PERIOD_END)
    repre.process_events(dict(points=[event]))


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


@pytest.mark.dependency()
def test_repre_velocity_not_touched(oneday_repre):
    assert oneday_repre.average_daily_velocity == 0
    assert oneday_repre.get_day_of_completion() is None
    assert np.all(oneday_repre.get_velocity_array() == 0)


@pytest.mark.dependency()
def test_repre_velocity_not_done(oneday_repre):
    oneday_repre.update(PERIOD_START, target.State.in_progress, points=1)
    assert oneday_repre.average_daily_velocity == 0
    assert oneday_repre.get_day_of_completion() is None
    assert np.all(oneday_repre.get_velocity_array() == 0)


@pytest.fixture
def twoday_repre_done_in_day(twoday_repre):
    twoday_repre.update(PERIOD_START, target.State.in_progress, points=2)
    twoday_repre.update(PERIOD_START + ONE_DAY, target.State.done, points=2)
    return twoday_repre


@pytest.mark.dependency(depends=["test_repre_velocity_not_done"])
def test_repre_velocity_done_in_day(twoday_repre_done_in_day):
    assert twoday_repre_done_in_day.average_daily_velocity == 2


@pytest.mark.dependency(depends=["test_repre_velocity_not_done"])
def test_repre_velocity_done_real_quick(twoday_repre):
    twoday_repre.update(PERIOD_START, target.State.done, points=2)
    twoday_repre.update(PERIOD_START + ONE_DAY, target.State.done, points=2)
    assert twoday_repre.average_daily_velocity == 2
    assert twoday_repre.get_day_of_completion() == PERIOD_START


@pytest.mark.dependency(depends=["test_repre_velocity_done_real_quick"])
def test_repre_velocity_done_real_quick_array(twoday_repre):
    twoday_repre.update(PERIOD_START, target.State.done, points=2)
    twoday_repre.update(PERIOD_START + ONE_DAY, target.State.done, points=2)
    velocity_array = twoday_repre.get_velocity_array()
    assert velocity_array.sum() == 2
    assert (velocity_array > 0).sum() == 1


def update_repre_with_casual_task_schedule(repre, start):
    repre.update(start, target.State.todo)
    repre.update(start + 1 * ONE_DAY, target.State.in_progress)
    repre.update(start + 2 * ONE_DAY, target.State.in_progress)
    repre.update(start + 3 * ONE_DAY, target.State.in_progress)
    repre.update(start + 4 * ONE_DAY, target.State.review)
    repre.update(start + 5 * ONE_DAY, target.State.review)


@pytest.mark.dependency(depends=["test_repre_velocity_done_in_day"])
def test_full_repre_velocity_done_in_three_days(repre):
    period_end = repre.end
    repre.update(period_end, target.State.done, points=9)
    repre.fill_history_from(period_end)
    update_repre_with_casual_task_schedule(repre, PERIOD_START)
    assert repre.average_daily_velocity == 3


@pytest.mark.dependency(depends=["test_repre_velocity_not_done"])
def test_task_done_retroactively(repre):
    update_repre_with_casual_task_schedule(repre, PERIOD_START)
    repre.update(PERIOD_START + 6 * ONE_DAY, target.State.done, points=9)
    for day in range(6):
        assert not repre.is_done(PERIOD_START + day * ONE_DAY)
    assert not repre.is_done(PERIOD_START - day * ONE_DAY)
    assert repre.is_done(repre.end)
    assert repre.is_done(PERIOD_START + 6 * ONE_DAY)
    assert repre.get_day_of_completion() == PERIOD_START + 6 * ONE_DAY


@pytest.mark.dependency(depends=["test_full_repre_velocity_done_in_three_days"])
def test_unknown_repre_velocity_done_in_three_days(repre):
    update_repre_with_casual_task_schedule(repre, PERIOD_START)
    repre.update(PERIOD_START + 6 * ONE_DAY, target.State.done, points=9)
    assert repre.average_daily_velocity == 3


@pytest.fixture
def simple_target():
    ret = target.BaseTarget()
    ret.name = "task"
    ret.point_cost = 8
    return ret


@pytest.fixture
def supertask_target(simple_target):
    ret = target.BaseTarget()
    ret.name = "supertask"
    ret.add_element(simple_target)
    return ret


@pytest.fixture
def another_supertask_target(simple_target):
    ret = target.BaseTarget()
    ret.name = "another-supertask"
    subtask = simple_target
    subtask.name = "subtask"
    ret.add_element(subtask)
    return ret


@pytest.fixture
def simple_long_period_aggregation(simple_target):
    start = PERIOD_START
    end = LONG_PERIOD_END
    ret = tm.Aggregation.from_target(simple_target, start, end)
    return ret


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

    next_subtask = target.BaseTarget()
    next_subtask.name = "next_subtask"
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


def test_aggregation_point_velocity_array(twoday_repre_done_in_day):
    a = tm.Aggregation()
    assert len(a.get_velocity_array()) == 0

    a.add_repre(twoday_repre_done_in_day)
    assert np.all(a.get_velocity_array() == twoday_repre_done_in_day.get_velocity_array())


def test_aggregation_point_velocity_trivial(twoday_repre_done_in_day):
    a = tm.Aggregation()
    assert a.point_velocity.expected == 0

    a.add_repre(twoday_repre_done_in_day)
    assert a.point_velocity.expected == 1
    assert a.point_velocity.sigma == pytest.approx(1)
