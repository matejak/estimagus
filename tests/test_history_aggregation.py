import datetime

import pytest
import numpy as np
import numpy.testing

from estimage import history, data
import estimage.history.aggregation as tm
import estimage.entities.card as card

from test_events import mgr, early_event, ONE_DAY, PERIOD_START, LONG_PERIOD_END
from test_history_progress import simple_card, repre, oneday_repre, twoday_repre, twoday_repre_done_in_day, ExtendedStatuses


@pytest.fixture
def supertask_card(simple_card):
    ret = card.BaseCard("supertask")
    ret.add_element(simple_card)
    return ret


@pytest.fixture
def another_supertask_card(simple_card):
    ret = card.BaseCard("another-supertask")
    subtask = simple_card
    subtask.name = "subtask"
    ret.add_element(subtask)
    return ret


def test_aggregation(repre):
    someday = datetime.datetime(2022, 10, 10)
    day_after = someday + ONE_DAY

    repre.update(day_after, points=6, status="in_progress")

    aggregation = tm.Aggregation()
    aggregation.add_repre(repre)
    aggregation.add_repre(repre)

    assert aggregation.statuses_on(someday) == {repre.get_status_at(someday)}
    assert aggregation.statuses_on(someday) != {repre.get_status_at(day_after)}

    assert aggregation.points_on(someday) == 2 * repre.get_points_at(someday)
    assert aggregation.points_on(day_after) == 2 * repre.get_points_at(day_after)


def test_aggregation_no_time_bounds():
    aggregation = tm.Aggregation()
    assert aggregation.start is None
    assert aggregation.end is None
    assert aggregation.days == 0


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


def check_repre_against_card(card, repre, start, end):
    assert repre.start == start
    assert repre.end == end
    assert repre.task_name == card.name
    assert repre.get_points_at(start) == card.point_cost
    assert repre.get_status_at(start).name == card.status


def test_simple_card_to_aggregation(simple_card):
    start = PERIOD_START
    end = PERIOD_START

    aggregation = tm.Aggregation.from_card(simple_card, start, end)
    assert len(aggregation.repres) == 1
    repre = aggregation.repres[0]

    check_repre_against_card(simple_card, repre, start, end)


def test_simple_card_to_aggregation_long(simple_card):
    start = PERIOD_START
    end = LONG_PERIOD_END

    aggregation = tm.Aggregation.from_card(simple_card, start, end)
    assert len(aggregation.repres) == 1
    repre = aggregation.repres[0]

    check_repre_against_card(simple_card, repre, start, end)


def test_supertask_to_aggregation_long(supertask_card):
    start = PERIOD_START
    end = LONG_PERIOD_END

    aggregation = tm.Aggregation.from_card(supertask_card, start, end)
    assert len(aggregation.repres) == 1
    repre = aggregation.repres[0]

    check_repre_against_card(supertask_card.children[0], repre, start, end)


def test_supertask_with_more_subtasks_to_aggregation_long(supertask_card):
    start = PERIOD_START
    end = LONG_PERIOD_END

    next_subtask = card.BaseCard("next_subtask")
    supertask_card.add_element(next_subtask)

    aggregation = tm.Aggregation.from_card(supertask_card, start, end)
    assert len(aggregation.repres) == 2

    check_repre_against_card(supertask_card.children[0], aggregation.repres[0], start, end)
    check_repre_against_card(supertask_card.children[1], aggregation.repres[1], start, end)


def test_supertasks_to_aggregation_long(supertask_card, another_supertask_card):
    start = PERIOD_START
    end = LONG_PERIOD_END

    aggregation = tm.Aggregation.from_cards(
        [supertask_card, another_supertask_card], start, end)
    assert len(aggregation.repres) == 2

    check_repre_against_card(supertask_card.children[0], aggregation.repres[0], start, end)
    check_repre_against_card(another_supertask_card.children[0], aggregation.repres[1], start, end)


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
    another_repre.status_timeline.set_value_at(a.start, a.statuses.int("todo"))
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


def test_card_span_propagates_to_children():
    END = PERIOD_START + 5 * ONE_DAY
    parent = card.BaseCard("p")
    parent.work_span = (PERIOD_START + ONE_DAY, END)
    child = card.BaseCard("c")
    parent.add_element(child)

    r = get_standard_span_progress(parent, END)
    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 1

    parent.work_span = (None, END - ONE_DAY)
    r = get_standard_span_progress(parent, END)
    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 0.75
    assert r.remainder_timeline.value_at(END - ONE_DAY) == 0

    parent.work_span = (PERIOD_START + ONE_DAY, None)
    r = get_standard_span_progress(parent, END)
    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 1.0
    assert r.remainder_timeline.value_at(END) == 0


def get_standard_span_progress(card, end):
    statuses = ExtendedStatuses()
    ret = tm.convert_card_to_representations_of_leaves(card, PERIOD_START, end, statuses)[0]
    return ret


def test_card_span_incomplete_works():
    END = PERIOD_START + 5 * ONE_DAY
    t = card.BaseCard("")
    t.work_span = (None, END - ONE_DAY)
    r = get_standard_span_progress(t, END)
    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 0.75
    assert r.remainder_timeline.value_at(END - ONE_DAY) == 0

    t.work_span = (None, PERIOD_START - ONE_DAY)
    r = get_standard_span_progress(t, END)

    t.work_span = (END + ONE_DAY, END + ONE_DAY)
    r = get_standard_span_progress(t, END)
    assert r.remainder_timeline.value_at(PERIOD_START) == 1
    assert r.remainder_timeline.value_at(END - ONE_DAY) == 1
    assert r.remainder_timeline.value_at(END) == 1

    t.work_span = (PERIOD_START - 5 * ONE_DAY, END + 5 * ONE_DAY)
    r = get_standard_span_progress(t, END)
    assert r.remainder_timeline.value_at(PERIOD_START) == pytest.approx(2 / 3)
    assert r.remainder_timeline.value_at(END) == pytest.approx(1 / 3)


def test_card_span_not_started_works():
    END = PERIOD_START + 5 * ONE_DAY
    t = card.BaseCard("")

    t.work_span = (PERIOD_START - ONE_DAY, PERIOD_START - ONE_DAY)
    r = get_standard_span_progress(t, END)
    assert r.remainder_timeline.value_at(END) == 0
    assert r.remainder_timeline.value_at(PERIOD_START) == 0

    t.work_span = (PERIOD_START - ONE_DAY, PERIOD_START + ONE_DAY)
    r = get_standard_span_progress(t, END)
    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 0
    assert r.remainder_timeline.value_at(PERIOD_START) == 0.5


def test_card_span_propagates():
    END = PERIOD_START + 5 * ONE_DAY
    t = card.BaseCard("")
    r = get_standard_span_progress(t, END)

    assert r.remainder_timeline.value_at(PERIOD_START) == 1
    assert r.remainder_timeline.value_at(END) == 0

    t.work_span = (PERIOD_START + 2 * ONE_DAY, END - ONE_DAY)
    r = get_standard_span_progress(t, END)

    assert r.remainder_timeline.value_at(PERIOD_START) == 1
    assert r.remainder_timeline.value_at(END) == 0

    assert r.remainder_timeline.value_at(PERIOD_START + ONE_DAY) == 1
    assert r.remainder_timeline.value_at(END - ONE_DAY) == 0

    assert r.remainder_timeline.value_at(PERIOD_START + 2 * ONE_DAY) == 1
    assert r.remainder_timeline.value_at(PERIOD_START + 3 * ONE_DAY) == 0.5


def test_card_span_starting_before_is_correctly_recalculated():
    END = PERIOD_START + 5 * ONE_DAY
    t = card.BaseCard("")
    t.work_span = (PERIOD_START - ONE_DAY, END - ONE_DAY)
    r = get_standard_span_progress(t, END)
    assert r.remainder_timeline.value_at(PERIOD_START) == 0.8


def test_card_span_ending_after_is_recalculated():
    END = PERIOD_START + 5 * ONE_DAY
    t = card.BaseCard("")
    t.work_span = (PERIOD_START + ONE_DAY, END + ONE_DAY)
    r = get_standard_span_progress(t, END)
    overflowing_ratio = ONE_DAY / (t.work_span[1] - t.work_span[0])
    assert r.remainder_timeline.value_at(END) == pytest.approx(overflowing_ratio)


@pytest.fixture
def simple_long_period_aggregation(simple_card):
    start = PERIOD_START
    end = LONG_PERIOD_END
    ret = tm.Aggregation.from_card(simple_card, start, end)
    return ret


def add_status_event_days_after_start(mgr, card, days, before, after):
    date = PERIOD_START + datetime.timedelta(days=days)
    evt = data.Event(card.name, "state", date)
    evt.value_before = before
    evt.value_after = after
    mgr.add_event(evt)


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


def test_aggregation_and_event_manager(mgr, simple_long_period_aggregation, simple_card, early_event):
    early_event.quantity = "points"
    simple_long_period_aggregation.process_event_manager(mgr)
    repre = simple_long_period_aggregation.repres[0]
    assert repre.get_points_at(PERIOD_START) == repre.get_points_at(LONG_PERIOD_END)
    assert repre.get_points_at(PERIOD_START) == simple_card.point_cost

    early_event.task_name = simple_card.name + "---"
    mgr.add_event(early_event)
    simple_long_period_aggregation.process_event_manager(mgr)
    repre = simple_long_period_aggregation.repres[0]
    assert repre.get_points_at(PERIOD_START) == repre.get_points_at(LONG_PERIOD_END)
    assert repre.get_points_at(PERIOD_START) == simple_card.point_cost

    early_event.task_name = simple_card.name
    early_event.value_after = "99"
    mgr.add_event(early_event)
    simple_long_period_aggregation.process_event_manager(mgr)
    repre = simple_long_period_aggregation.repres[0]
    assert repre.get_points_at(LONG_PERIOD_END) == float(early_event.value_after)
    assert repre.get_points_at(PERIOD_START) == float(early_event.value_before)


def get_wip_aggregation(simple_card, mgr):
    simple_card.status = "in_progress"
    add_status_event_days_after_start(
        mgr, simple_card, 10, "todo", "in_progress")
    aggregation = tm.Aggregation.from_card(simple_card, PERIOD_START, LONG_PERIOD_END)
    aggregation.process_event_manager(mgr)
    return aggregation


def get_done_aggregation(simple_card, mgr, was_underway_for_days):
    simple_card.status = "done"
    add_status_event_days_after_start(
        mgr, simple_card, 10, "todo", "in_progress")
    add_status_event_days_after_start(
        mgr, simple_card, 10 + was_underway_for_days, "in_progress", "done")
    aggregation = tm.Aggregation.from_card(simple_card, PERIOD_START, LONG_PERIOD_END)
    aggregation.process_event_manager(mgr)
    return aggregation


def test_aggregation_summary(simple_card, mgr):
    a = get_wip_aggregation(simple_card, mgr)
    summary = tm.Summary(a, LONG_PERIOD_END)
    assert summary.initial_todo == simple_card.point_cost
    assert summary.total_days_in_period == (LONG_PERIOD_END - PERIOD_START).days + 1
    assert summary.cutoff_todo == 0
    assert summary.cutoff_underway == simple_card.point_cost


def test_aggregation_done_summary(simple_card, mgr):
    a = get_done_aggregation(simple_card, mgr, 1)
    summary = tm.Summary(a, LONG_PERIOD_END)
    assert summary.initial_todo == simple_card.point_cost
    assert summary.total_points_done == simple_card.point_cost


def test_aggregation_velocity_summary(simple_card, mgr):
    a = get_done_aggregation(simple_card, mgr, 0)
    summary = tm.Summary(a, LONG_PERIOD_END)
    assert summary.total_days_with_velocity == 1
    assert summary.nonzero_velocity == simple_card.point_cost
    mean_velocity = summary.daily_velocity
    assert 0 < mean_velocity < summary.nonzero_velocity

    mgr.erase()
    a = get_done_aggregation(simple_card, mgr, 2)
    summary = tm.Summary(a, LONG_PERIOD_END)
    assert summary.total_days_with_velocity == 2
    assert summary.nonzero_velocity == simple_card.point_cost / 2.0
    assert mean_velocity == summary.daily_velocity
