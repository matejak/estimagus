import datetime

import pytest

import estimage.history.timeline as tm
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
    assert long_timeline.value_at(late_event.time) == 0
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
    assert long_timeline.value_at(late_event.time) == 0
    assert long_timeline.value_at(late_event.time + ONE_DAY) == 0
    assert long_timeline.value_at(less_early_event.time) == 10
