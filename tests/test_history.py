import datetime

import pytest
import numpy as np

import app.history as tm


ONE_DAY = datetime.timedelta(days=1)


def test_timeline():
    start = datetime.datetime(2022, 10, 1)
    end = datetime.datetime(2022, 10, 21)
    timeline = tm.Timeline(start, end)
    assert timeline.days == 21


def test_events():
    start = datetime.datetime(2022, 10, 1)
    end = datetime.datetime(2022, 10, 21)
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
    start = datetime.datetime(2022, 10, 1)
    end = datetime.datetime(2022, 10, 21)

    representation = tm.Repre(start, end)
    return representation


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
