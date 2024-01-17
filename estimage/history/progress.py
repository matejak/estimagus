import datetime
import typing
import collections

import numpy as np

from .. import data
from ..entities import status
from . import timeline


ONE_DAY = datetime.timedelta(days=1)


def days_between(
        start: datetime.datetime, evt: datetime.datetime):
    return (evt - start).days


class Progress:
    start: datetime.datetime
    end: datetime.datetime
    points_timeline: timeline.Timeline
    status_timeline: timeline.Timeline
    remainder_timeline: timeline.Timeline
    time_timeline: timeline.Timeline
    relevancy_timeline: timeline.Timeline
    task_name: str

    def __init__(self, start, end, statuses=None):
        self.start = start
        self.end = end

        self.statuses = statuses
        if self.statuses is None:
            self.statuses = status.Statuses()
        self.points_timeline = timeline.Timeline(start, end)
        self.status_timeline = timeline.Timeline(start, end)
        self.status_timeline.recreate_with_value(self.statuses.int("irrelevant"), int)
        self.time_timeline = timeline.Timeline(start, end)

        self.remainder_timeline = timeline.Timeline(start, end)
        self.calculate_plan()

        self.relevancy_timeline = timeline.Timeline(start, end)
        self.relevancy_timeline.recreate_with_value(1)
        self.task_name = ""

    def calculate_plan(self, work_start=None, work_end=None):
        start = work_start or self.start
        end = work_end or self.end
        self.remainder_timeline.set_gradient_values(start, 1, end, 0)

    def update(self, when, status=None, points=None, time=None):
        if points is not None:
            self.points_timeline.set_value_at(when, points)
        if status is not None:
            self.status_timeline.set_value_at(when, self.statuses.int(status))
        if time is not None:
            self.time_timeline.set_value_at(when, status)

    def get_points_at(self, when):
        if not self.relevancy_timeline.value_at(when):
            return 0
        return self.points_timeline.value_at(when)

    def always_was_irrelevant(self):
        relevant_statuses = self.statuses.that_have_properties(relevant=True, done=False)
        codes = self.statuses.get_ints(relevant_statuses)
        relevant_mask = self.status_timeline.get_value_mask(codes[0])
        for code in codes[1:]:
            relevant_mask |= self.status_timeline.get_value_mask(code)
        if sum(relevant_mask):
            return False
        return True

    def get_last_point_value(self):
        nonzero_mask = np.logical_not(self.points_timeline.get_value_mask(0))
        if sum(nonzero_mask) == 0:
            return 0
        ret = self.points_timeline.get_masked_values(nonzero_mask)[-1]
        return ret

    def get_status_at(self, when):
        index = self.status_timeline.value_at(when)
        status = self.statuses.statuses[index]
        if not self.relevancy_timeline.value_at(when) and status.relevant:
            return self.statuses.get("irrelevant")
        return status

    def set_status_at(self, when, status):
        status_meaning = self.statuses.get(status)
        self.relevancy_timeline.set_value_at(when, status_meaning.relevant)
        self.status_timeline.set_value_at(when, self.statuses.int(status))

    def status_is(self, status: str):
        status_int = self.statuses.int(status)
        return self.status_timeline.get_value_mask(status_int)

    def points_of_status(self, status):
        mask = self.status_is(status)
        return self.points_timeline.get_masked_values(mask)

    def fill_history_from(self, when):
        init_event = data.Event("", "points", when)

        value = self.points_timeline.value_at(when)
        init_event.value_before = value
        self.points_timeline.process_events([init_event])
        self.points_timeline.set_value_at(when, value)

        status_int = self.status_timeline.value_at(when)
        init_event.value_after = None
        init_event.value_before = status_int
        self.status_timeline.process_events([init_event])
        self.status_timeline.set_value_at(when, status_int)

    def is_done(self, latest_at=None):
        relevant_slice = slice(0, None)
        if latest_at is not None:
            if latest_at < self.start:
                return False
            elif latest_at < self.end:
                deadline_index = days_between(self.start, latest_at)
                relevant_slice = slice(0, deadline_index + 1)
        done_mask = self.status_timeline.get_value_mask(self.statuses.int("done"))[relevant_slice]
        task_done = done_mask.sum() > 0
        return task_done

    def points_completed(self, before=None):
        if not self.is_done(before):
            return 0
        done_mask = self.status_timeline.get_value_mask(self.statuses.int("done"))
        task_points = self.points_timeline.get_masked_values(done_mask)[-1]
        return task_points

    @property
    def average_daily_velocity(self):
        in_progress_mask = self._get_value_mask_of_in_progress()
        time_taken = in_progress_mask.sum() or 1
        return self.points_completed() / time_taken

    def get_day_of_completion(self):
        done_mask = self.status_timeline.get_value_mask(self.statuses.int("done"))
        if done_mask.sum() == 0:
            return None
        indices = np.arange(len(done_mask))
        days_from_start_to_completion = indices[done_mask][0]
        return self.start + ONE_DAY * days_from_start_to_completion

    def get_plan_array(self):
        points_multiplier = self.get_last_point_value()
        if self.always_was_irrelevant():
            points_multiplier *= 0
        return self.remainder_timeline.get_array() * points_multiplier

    def _get_value_mask_of_in_progress(self):
        relevant_statuses = self.statuses.that_have_properties(relevant=True, wip=True)
        codes = self.statuses.get_ints(relevant_statuses)
        relevant_mask = self.status_timeline.get_value_mask(codes[0])
        for code in codes[1:]:
            relevant_mask |= self.status_timeline.get_value_mask(code)
        return relevant_mask

    def get_velocity_array(self):
        if not self.is_done():
            return self.status_timeline.get_value_mask(self.statuses.int("done")).astype(float)
        velocity_array = self._get_value_mask_of_in_progress().astype(float)
        if velocity_array.sum() == 0:
            index_of_completion = days_between(self.start, self.get_day_of_completion())
            if index_of_completion == 0:
                return velocity_array
            velocity_array[index_of_completion] = 1
        velocity_array *= self.points_completed() / velocity_array.sum()
        return velocity_array

    def _extract_time_relevant_events(self, events: typing.Iterable[data.Event]):
        return [
            evt for evt in events if self.start <= evt.time <= self.end
        ]

    def process_events(self, events: typing.List[data.Event]):
        events_by_type = collections.defaultdict(list)
        for evt in events:
            events_by_type[evt.quantity].append(evt)
        self.process_events_by_type(events_by_type)

    def process_events_by_type(self, events_by_type: typing.Mapping[str, typing.List[data.Event]]):
        TYPES_TO_TIMELINE = {
            "time": self.time_timeline,
            "points": self.points_timeline,
            "state": self.status_timeline,
            "project": self.relevancy_timeline,
        }
        for status_event in events_by_type.get("state", frozenset()):
            val = status_event.value_before
            status_event.value_before = self.statuses.int(val)
            val = status_event.value_after
            status_event.value_after = self.statuses.int(val)

        for event_type, tline in TYPES_TO_TIMELINE.items():
            events = events_by_type.get(event_type, [])
            events = self._extract_time_relevant_events(events)
            tline.process_events(events)
