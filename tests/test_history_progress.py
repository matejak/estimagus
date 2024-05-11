import datetime

import pytest
import numpy as np
import numpy.testing

from estimage import history, data
import estimage.history.progress as tm
from estimage.entities import card, status

from test_events import early_event, less_early_event, late_event, ONE_DAY, PERIOD_START, LONG_PERIOD_END


LATER = PERIOD_START + datetime.timedelta(days=9)


class ExtendedStatuses(status.Statuses):
    def __init__(self):
        super().__init__()
        self.statuses.extend([
            status.Status.create("backlog", relevant=False),
            status.Status.create("abandoned", relevant=False, started=True),
            status.Status.create("review", wip=False, started=True, done=False),
        ])


def test_irrelevant_statuses():
    statuses = ExtendedStatuses()
    wip_statuses = statuses.that_have_properties(wip=True)
    assert len(wip_statuses) == 1
    assert wip_statuses[0].name == "in_progress"

    irrelevant_statuses = statuses.that_have_properties(relevant=False)
    assert len(irrelevant_statuses) == 3
    assert irrelevant_statuses[0].name == "irrelevant"
    assert irrelevant_statuses[1].name == "backlog"
    assert statuses.get_ints(irrelevant_statuses) == [0, 4, 5]

    incomplete_statuses = statuses.that_have_properties(started=True, done=False)
    assert len(incomplete_statuses) == 3
    assert incomplete_statuses[0].name == "in_progress"
    assert incomplete_statuses[1].name == "abandoned"
    assert incomplete_statuses[2].name == "review"


@pytest.fixture
def repre():
    start = PERIOD_START
    end = LONG_PERIOD_END

    progress = tm.Progress(start, end)
    progress.statuses = ExtendedStatuses()
    return progress


@pytest.fixture
def twoday_repre():
    start = PERIOD_START
    end = PERIOD_START + ONE_DAY

    progress = tm.Progress(start, end)
    return progress


@pytest.fixture
def oneday_repre():
    start = PERIOD_START
    end = PERIOD_START

    progress = tm.Progress(start, end)
    # representation.set_status_at(end, "in_progress")
    # representation.fill_history_from(end)
    return progress


@pytest.fixture
def twoday_repre_done_in_day(twoday_repre):
    twoday_repre.update(PERIOD_START, "in_progress", points=2)
    twoday_repre.update(PERIOD_START + ONE_DAY, "done", points=2)
    return twoday_repre


@pytest.mark.dependency()
def test_repre_velocity_not_touched(oneday_repre):
    assert oneday_repre.average_daily_velocity == 0
    assert oneday_repre.get_day_of_completion() is None
    assert np.all(oneday_repre.get_velocity_array() == 0)


@pytest.mark.dependency()
def test_repre_velocity_not_done(oneday_repre):
    oneday_repre.update(PERIOD_START, "in_progress", points=1)
    assert oneday_repre.average_daily_velocity == 0
    assert oneday_repre.get_day_of_completion() is None
    assert np.all(oneday_repre.get_velocity_array() == 0)


@pytest.fixture
def fiveday_repre():
    start = PERIOD_START
    end = PERIOD_START + 4 * ONE_DAY

    progress = tm.Progress(start, end)
    return progress


def test_repre(repre):
    someday = LATER
    day_after = someday + ONE_DAY

    repre.update(someday, points=5, status="in_progress")

    assert repre.get_points_at(someday) == 5
    assert repre.get_status_at(someday).name == "in_progress"
    assert sum(repre.status_is("in_progress")) == 1

    assert repre.get_points_at(someday - ONE_DAY) == 0
    assert repre.get_status_at(someday + ONE_DAY).name == "irrelevant"
    assert repre.get_status_at(someday - ONE_DAY).name == "irrelevant"

    repre.fill_history_from(someday)
    assert sum(repre.status_is("in_progress")) == 10
    assert sum(repre.status_is("review")) == 0

    assert repre.get_points_at(someday - ONE_DAY) == 5
    assert repre.get_status_at(someday - ONE_DAY).name == "in_progress"

    repre.update(day_after, points=6, status="review")

    assert repre.get_points_at(someday) == 5
    assert repre.get_status_at(someday).name == "in_progress"
    assert repre.get_points_at(day_after) == 6
    assert repre.get_status_at(day_after).name == "review"

    assert sum(repre.status_is("review")) == 1
    assert repre.points_of_status("review").max() == 6

    assert sum(repre.status_is("in_progress")) == 10
    assert repre.points_of_status("in_progress").max() == 5


def test_repre_get_last_point_value():
    r = tm.Progress(PERIOD_START, LONG_PERIOD_END)
    assert r.get_last_point_value() == 0

    r.points_timeline.set_value_at(PERIOD_START, 1.0)
    assert r.get_last_point_value() == 1

    r.points_timeline.set_value_at(PERIOD_START + ONE_DAY, 2.0)
    assert r.get_last_point_value() == 2

    r.points_timeline.set_value_at(PERIOD_START + 2 * ONE_DAY, 1.0)
    assert r.get_last_point_value() == 1

    r.points_timeline.set_value_at(PERIOD_START + 2 * ONE_DAY, 0)
    assert r.get_last_point_value() == 2


def test_repre_plan(twoday_repre_done_in_day):
    points = twoday_repre_done_in_day.get_points_at(PERIOD_START)
    plan = twoday_repre_done_in_day.get_plan_array()
    assert plan[-1] == 0
    assert plan[0] == points


def test_irrelevant_repre():
    r = tm.Progress(PERIOD_START, LONG_PERIOD_END)
    r.statuses = ExtendedStatuses()
    assert r.always_was_irrelevant()

    r.set_status_at(PERIOD_START, "todo")
    assert not r.always_was_irrelevant()

    r.set_status_at(PERIOD_START + ONE_DAY, "in_progress")
    assert not r.always_was_irrelevant()

    r.set_status_at(PERIOD_START, "abandoned")
    assert not r.always_was_irrelevant()
    assert r.get_status_at(PERIOD_START).name == "abandoned"

    r.set_status_at(PERIOD_START + ONE_DAY, "done")
    assert r.always_was_irrelevant()

    r.set_status_at(PERIOD_START, "review")
    assert not r.always_was_irrelevant()


def test_project_events(repre, early_event, late_event):
    points_event = data.Event("", "points", PERIOD_START)
    points_event.value_before = 5
    points_event.value_after = 5

    status_event = data.Event("", "state", PERIOD_START)
    status_event.value_before = "backlog"
    status_event.value_after = "todo"

    early_event.quantity = "project"
    early_event.value_before = 0
    early_event.value_after = 1

    late_event.quantity = "project"
    late_event.value_before = 1
    late_event.value_after = 0

    repre.process_events([points_event, status_event, late_event, early_event])
    assert repre.get_points_at(PERIOD_START) == 0
    assert repre.get_status_at(PERIOD_START).name == "irrelevant"
    assert repre.get_points_at(early_event.time + ONE_DAY) == 5
    assert repre.get_status_at(early_event.time + ONE_DAY).name == "todo"
    assert repre.get_points_at(late_event.time + ONE_DAY) == 0
    assert repre.get_status_at(late_event.time + ONE_DAY).name == "irrelevant"


def test_repre_has_sane_plan(oneday_repre, twoday_repre, fiveday_repre):
    assert oneday_repre.remainder_timeline.value_at(oneday_repre.end) == 0

    assert twoday_repre.remainder_timeline.value_at(twoday_repre.start) == 1
    assert twoday_repre.remainder_timeline.value_at(twoday_repre.end) == 0

    assert fiveday_repre.remainder_timeline.value_at(fiveday_repre.start) == 1
    assert fiveday_repre.remainder_timeline.value_at(fiveday_repre.start + 2 * ONE_DAY) == 0.5
    assert fiveday_repre.remainder_timeline.value_at(fiveday_repre.end) == 0


def test_timeline_interpolation_sanity():
    short_timeline = history.Timeline(PERIOD_START, PERIOD_START)
    short_timeline.set_gradient_values(PERIOD_START, 0, PERIOD_START, 0)
    assert short_timeline.value_at(PERIOD_START) == 0

    short_timeline.set_gradient_values(PERIOD_START, 0, PERIOD_START, 2)
    assert short_timeline.value_at(PERIOD_START) == 2


def test_timeline_interpolation():
    END = PERIOD_START + 5 * ONE_DAY
    reasonable_timeline = history.Timeline(PERIOD_START, END)

    reasonable_timeline.set_gradient_values(PERIOD_START, 1, END, 1)
    assert sum(reasonable_timeline.get_value_mask(1)) == 6

    reasonable_timeline.set_gradient_values(PERIOD_START, 0, PERIOD_START + 2 * ONE_DAY, 1)
    assert reasonable_timeline.value_at(PERIOD_START) == 0
    assert reasonable_timeline.value_at(PERIOD_START + 2 * ONE_DAY) == 1
    assert reasonable_timeline.value_at(PERIOD_START + ONE_DAY) == 0.5


def test_timeline_interpolation_invalid():
    END = PERIOD_START + 5 * ONE_DAY
    reasonable_timeline = history.Timeline(PERIOD_START, END)
    reasonable_timeline.set_gradient_values(PERIOD_START, 1, PERIOD_START, 0)
    assert sum(reasonable_timeline.get_array()) == 0

    reasonable_timeline.set_gradient_values(PERIOD_START, 1, PERIOD_START + 10 * ONE_DAY, 1)
    assert sum(reasonable_timeline.get_value_mask(1)) == 6

    reasonable_timeline.set_gradient_values(PERIOD_START, 0, PERIOD_START + 10 * ONE_DAY, 1)
    assert 0.2 < reasonable_timeline.get_array().mean() < 0.4

    reasonable_timeline.set_gradient_values(PERIOD_START - 10 * ONE_DAY, 0, END, 1)
    assert 0.6 < reasonable_timeline.get_array().mean() < 1


def test_card_span_of_executive_summary():
    pytest.skip()
    END = PERIOD_START + 5 * ONE_DAY
    parent = card.BaseCard()
    parent.work_span = (PERIOD_START + ONE_DAY, END)
    child = card.BaseCard()
    parent.add_element(child)
    assert summary.completion == "grey zone"


def test_localize_events(early_event, less_early_event, late_event):
    early_loc = tm.days_between(PERIOD_START, early_event.time)
    less_early_loc = tm.days_between(PERIOD_START, less_early_event.time)

    assert int(early_loc) == early_loc
    assert int(less_early_loc) == less_early_loc

    assert early_loc <= less_early_loc
    assert early_loc < tm.days_between(PERIOD_START, late_event.time)

    assert tm.days_between(PERIOD_START, PERIOD_START) == 0


@pytest.mark.dependency(depends=["test_repre_velocity_not_done"])
def test_repre_velocity_done_in_day(twoday_repre_done_in_day):
    assert twoday_repre_done_in_day.average_daily_velocity == 2


def test_repre_zero_velocity_when_done_before_start(repre):
    repre.update(repre.end, points=5, status="done")
    repre.fill_history_from(repre.end)
    assert repre.get_velocity_array().max() == 0


@pytest.mark.dependency(depends=["test_repre_velocity_not_done"])
def test_repre_velocity_done_real_quick(twoday_repre):
    twoday_repre.update(PERIOD_START, "done", points=2)
    twoday_repre.update(PERIOD_START + ONE_DAY, "done", points=2)
    assert twoday_repre.average_daily_velocity == 2
    assert twoday_repre.get_day_of_completion() == PERIOD_START


@pytest.mark.dependency(depends=["test_repre_velocity_done_real_quick"])
def test_repre_velocity_done_real_quick_array(twoday_repre):
    twoday_repre.update(PERIOD_START, "todo", points=2)
    twoday_repre.update(PERIOD_START + ONE_DAY, "done", points=2)
    velocity_array = twoday_repre.get_velocity_array()
    assert velocity_array.sum() == 2
    assert (velocity_array > 0).sum() == 1


def update_repre_with_casual_task_schedule(repre, start):
    repre.update(start, "todo")
    repre.update(start + 1 * ONE_DAY, "in_progress")
    repre.update(start + 2 * ONE_DAY, "in_progress")
    repre.update(start + 3 * ONE_DAY, "in_progress")
    repre.update(start + 4 * ONE_DAY, "review")
    repre.update(start + 5 * ONE_DAY, "review")


@pytest.mark.dependency(depends=["test_repre_velocity_done_in_day"])
def test_full_repre_velocity_done_in_three_days(repre):
    period_end = repre.end
    repre.update(period_end, "done", points=9)
    repre.fill_history_from(period_end)
    update_repre_with_casual_task_schedule(repre, PERIOD_START)
    assert repre.average_daily_velocity == 3


@pytest.mark.dependency(depends=["test_repre_velocity_not_done"])
def test_task_done_retroactively(repre):
    update_repre_with_casual_task_schedule(repre, PERIOD_START)
    repre.update(PERIOD_START + 6 * ONE_DAY, "done", points=9)
    for day in range(6):
        assert not repre.is_done(PERIOD_START + day * ONE_DAY)
    assert not repre.is_done(PERIOD_START - day * ONE_DAY)
    assert repre.is_done(repre.end)
    assert repre.is_done(PERIOD_START + 6 * ONE_DAY)
    assert repre.get_day_of_completion() == PERIOD_START + 6 * ONE_DAY


@pytest.mark.dependency(depends=["test_full_repre_velocity_done_in_three_days"])
def test_unknown_repre_velocity_done_in_three_days(repre):
    update_repre_with_casual_task_schedule(repre, PERIOD_START)
    repre.update(PERIOD_START + 6 * ONE_DAY, "done", points=9)
    assert repre.average_daily_velocity == 3


def test_out_of_bounds_events_ignored(repre):
    too_early = PERIOD_START - ONE_DAY
    too_late = LONG_PERIOD_END + ONE_DAY

    event = data.Event("", "points", too_early)
    repre.process_events([event])

    event = data.Event("", "points", too_late)
    repre.process_events([event])


def test_out_of_bounds_events_ok(repre):
    event = data.Event("", "points", PERIOD_START)
    repre.process_events([event])

    event = data.Event("", "points", LONG_PERIOD_END)
    repre.process_events([event])


def test_general_events(repre):
    someday = LATER
    day_after = someday + ONE_DAY
    day_before = someday - ONE_DAY

    assert repre.get_points_at(someday) == 0
    assert repre.get_status_at(someday).name == "irrelevant"
    assert repre.get_points_at(day_after) == 0
    assert repre.get_status_at(day_after).name == "irrelevant"

    last_measurement_points = data.Event.last_points_measurement("task_name", someday, 5)
    repre.process_events([last_measurement_points])

    assert repre.get_points_at(day_before) == 5
    assert repre.get_points_at(someday) == 5
    assert repre.get_points_at(day_after) == 5
    assert repre.points_completed(someday) == 0
    assert repre.points_completed(day_before) == 0


def test_solution_progress():
    end = PERIOD_START + ONE_DAY * 5
    issue_started_at = PERIOD_START + ONE_DAY * 1
    issue_done_at = PERIOD_START + ONE_DAY * 2
    t = card.BaseCard("T")
    t.point_cost = 5
    t.status = "done"
    r = history.aggregation.convert_card_to_representation(t, PERIOD_START, end, ExtendedStatuses())

    event_start = data.Event("T", "state", issue_started_at)
    event_start.value_before = "todo"
    event_start.value_after = "in_progress"

    event_end = data.Event("T", "state", issue_done_at)
    event_end.value_before = "in_progress"
    event_end.value_after = "done"

    events = dict(state=[event_start, event_end])
    r.process_events_by_type(events)
    status_array = r.status_timeline.get_array()
    assert r.get_status_at(PERIOD_START + 0 * ONE_DAY).name == "todo"
    assert r.get_status_at(PERIOD_START + 1 * ONE_DAY).name == "in_progress"
    assert r.get_status_at(PERIOD_START + 2 * ONE_DAY).name == "done"
    assert r.get_status_at(PERIOD_START + 3 * ONE_DAY).name == "done"
