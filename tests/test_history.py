import datetime

import pytest
import numpy as np

import estimage.history as tm


ONE_DAY = datetime.timedelta(days=1)
PERIOD_START = datetime.datetime(2022, 10, 1)
LONG_PERIOD_END = datetime.datetime(2022, 10, 21)


def test_timeline():
    start = PERIOD_START
    end = LONG_PERIOD_END
    timeline = tm.Timeline(start, end)
    assert timeline.days == 21


def test_timeline_masking():
    timeline = tm.Timeline(PERIOD_START, LONG_PERIOD_END)
    timeline.set_value_at(PERIOD_START + ONE_DAY, 55)
    mask = timeline.get_value_mask(55)
    assert sum(mask) == 1
    assert timeline.get_masked_values(mask)[0] == 55


def test_events():
    start = PERIOD_START
    end = LONG_PERIOD_END
    evt_early = datetime.datetime(2022, 10, 11, 12)
    evt_less_early = datetime.datetime(2022, 10, 11, 13)
    evt_late = datetime.datetime(2022, 10, 15)
    evtx = datetime.datetime(2023, 1, 1)

    assert tm.localize_event(start, evt_early) == 10
    index_late = 14
    assert tm.localize_event(start, evt_late) == index_late

    event_early = tm.Event("", evt_early)
    event_early.value = 15

    event_less_early = tm.Event("", evt_less_early)
    event_less_early.value = 17

    event_late = tm.Event("", evt_late)
    event_late.value = 10

    timeline = tm.Timeline(start, end)

    with pytest.raises(ValueError):
        timeline.process_events([tm.Event("", evtx)])

    timeline.process_events([event_early, event_late])
    assert timeline.value_at(end) == 0
    assert timeline.value_at(start) == 15
    assert timeline.value_at(evt_early + ONE_DAY * 2) == 10
    assert timeline.value_at(evt_late) == 10
    assert timeline.value_at(evt_late + ONE_DAY) == 0

    timeline.recreate_with_value(3, dtype=int)
    assert timeline.value_at(start) == timeline.value_at(end)
    assert timeline.value_at(start) == 3

    timeline.process_events([event_less_early, event_early, event_late])
    assert timeline.value_at(end) == 3
    assert timeline.value_at(start) == 15
    assert timeline.value_at(evt_early + ONE_DAY * 2) == 10
    assert timeline.value_at(evt_late) == 10
    assert timeline.value_at(evt_late + ONE_DAY) == 3
    assert timeline.value_at(evt_less_early) == 17


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


@pytest.fixture
def event_in_progress():
    ret = tm.Event("", PERIOD_START)
    ret.value = tm.State.in_progress
    return ret


@pytest.fixture
def event_review():
    ret = tm.Event("", PERIOD_START)
    ret.value = tm.State.review
    return ret


def test_repre(repre):
    someday = datetime.datetime(2022, 10, 10)
    day_after = someday + ONE_DAY

    repre.update(someday, points=5, status=tm.State.in_progress)

    assert repre.get_points_at(someday) == 5
    assert repre.get_status_at(someday) == tm.State.in_progress

    assert repre.get_points_at(someday - ONE_DAY) == 0
    assert repre.get_status_at(someday + ONE_DAY) == tm.State.unknown
    assert repre.get_status_at(someday - ONE_DAY) == tm.State.unknown

    repre.fill_history_from(someday)

    assert repre.get_points_at(someday - ONE_DAY) == 5
    assert repre.get_status_at(someday - ONE_DAY) == tm.State.in_progress

    repre.update(day_after, points=6, status=tm.State.review)

    assert repre.get_points_at(someday) == 5
    assert repre.get_status_at(someday) == tm.State.in_progress
    assert repre.get_points_at(day_after) == 6
    assert repre.get_status_at(day_after) == tm.State.review

    assert sum(repre.status_is(tm.State.review)) == 1
    assert repre.points_of_status(tm.State.review).max() == 6

    assert sum(repre.status_is(tm.State.in_progress)) == 10
    assert repre.points_of_status(tm.State.in_progress).max() == 5


def test_aggregation(repre):
    someday = datetime.datetime(2022, 10, 10)
    day_after = someday + ONE_DAY

    repre.update(day_after, points=6, status=tm.State.review)

    aggregation = tm.Aggregation()
    aggregation.add_repre(repre)
    aggregation.add_repre(repre)

    assert aggregation.states_on(someday) == {repre.get_status_at(someday)}
    assert aggregation.states_on(someday) != {repre.get_status_at(day_after)}

    assert aggregation.points_on(someday) == 2 * repre.get_points_at(someday)
    assert aggregation.points_on(day_after) == 2 * repre.get_points_at(day_after)


@pytest.mark.dependency()
def test_repre_velocity_not_done(oneday_repre):
    oneday_repre.update(PERIOD_START, tm.State.in_progress, points=1)
    assert oneday_repre.velocity == 0


@pytest.mark.dependency(depends=["test_repre_velocity_not_done"])
def test_repre_velocity_done_in_day(twoday_repre):
    twoday_repre.update(PERIOD_START, tm.State.in_progress, points=2)
    twoday_repre.update(PERIOD_START + ONE_DAY, tm.State.done, points=2)
    assert twoday_repre.velocity == 2


@pytest.mark.dependency(depends=["test_repre_velocity_not_done"])
def test_repre_velocity_done_real_quick(twoday_repre):
    twoday_repre.update(PERIOD_START, tm.State.done, points=2)
    twoday_repre.update(PERIOD_START + ONE_DAY, tm.State.done, points=2)
    assert twoday_repre.velocity == 2


@pytest.mark.dependency(depends=["test_repre_velocity_done_in_day"])
def test_full_repre_velocity_done_in_three_days(repre):
    period_end = repre.status_timeline.end
    repre.update(period_end, tm.State.done, points=9)
    repre.fill_history_from(period_end)
    repre.update(PERIOD_START, tm.State.todo)
    repre.update(PERIOD_START + 1 * ONE_DAY, tm.State.in_progress)
    repre.update(PERIOD_START + 2 * ONE_DAY, tm.State.in_progress)
    repre.update(PERIOD_START + 3 * ONE_DAY, tm.State.in_progress)
    repre.update(PERIOD_START + 4 * ONE_DAY, tm.State.review)
    repre.update(PERIOD_START + 5 * ONE_DAY, tm.State.review)
    assert repre.velocity == 3


@pytest.mark.dependency(depends=["test_full_repre_velocity_done_in_three_days"])
def test_unknown_repre_velocity_done_in_three_days(repre):
    repre.update(PERIOD_START, tm.State.todo)
    repre.update(PERIOD_START + 1 * ONE_DAY, tm.State.in_progress)
    repre.update(PERIOD_START + 2 * ONE_DAY, tm.State.in_progress)
    repre.update(PERIOD_START + 3 * ONE_DAY, tm.State.in_progress)
    repre.update(PERIOD_START + 4 * ONE_DAY, tm.State.review)
    repre.update(PERIOD_START + 5 * ONE_DAY, tm.State.review)
    repre.update(PERIOD_START + 6 * ONE_DAY, tm.State.done, points=9)
    assert repre.velocity == 3
