import datetime
import typing

import numpy as np

from .. import data


class Timeline:
    _data: np.array
    start: datetime.datetime
    end: datetime.datetime

    def __init__(self, start: datetime.datetime, end: datetime.datetime):
        self.start = start
        self.end = end
        period = end - start
        self._data = np.zeros(period.days + 1)

    def _localize_date(self, date: datetime.datetime) -> int:
        return (date - self.start).days

    def recreate_with_value(self, value, dtype=float):
        self._data = np.empty_like(self._data, dtype=dtype)
        self._data[:] = value

    def set_gradient_values(self,
                            start: datetime.datetime, start_value: float,
                            end: datetime.datetime, end_value: float):
        appropriate_start = max(start, self.start)
        appropriate_start = min(appropriate_start, self.end)
        appropriate_end = min(end, self.end)
        appropriate_end = max(appropriate_end, self.start)
        time_distance = (end - start).days
        if time_distance > 0:
            gradient = (end_value - start_value) / time_distance
            recalculated_start_value = (appropriate_start - start).days * gradient + start_value
            recalculated_end_value = (appropriate_end - start).days * gradient + start_value
        else:
            recalculated_start_value = start_value
            recalculated_end_value = end_value
        self._set_safe_gradient_values(appropriate_start, recalculated_start_value,
                                       appropriate_end, recalculated_end_value)

    def _set_safe_gradient_values(self,
                                  start: datetime.datetime, start_value: float,
                                  end: datetime.datetime, end_value: float):
        start_index = self._localize_date(start)
        end_index = self._localize_date(end) + 1
        values = np.linspace(start_value, end_value, end_index - start_index)
        self._data[start_index:end_index] = values
        self.set_value_at(start, start_value)
        self.set_value_at(end, end_value)

    def get_array(self) -> np.ndarray:
        return self._data.copy()

    @property
    def days(self) -> int:
        return len(self._data)

    def process_events(self, events: typing.Iterable[data.Event]):
        if not events:
            return
        events_from_oldest = sorted(events, key=lambda x: x.time)
        events_from_newest = events_from_oldest[::-1]
        newest_event = events_from_newest[0]
        if (filler_value := newest_event.value_after) is not None:
            self._data[:] = filler_value
        indices_from_newest = np.empty(len(events_from_newest), dtype=int)
        for i, e in enumerate(events_from_newest):
            index = self._localize_date(e.time)
            indices_from_newest[i] = index
            if not 0 <= index < len(self._data):
                msg = "Event outside of the timeline"
                raise ValueError(msg)
            self._data[0:index] = e.value_before

        conservative_event_handling = False
        if conservative_event_handling:
            indices_from_oldest = indices_from_newest[::-1]
            for i, e in zip(indices_from_oldest, events_from_oldest):
                self._data[i] = e.value_before

    def set_value_at(self, time: datetime.datetime, value):
        index = self._localize_date(time)
        self._data[index] = value

    def value_at(self, time: datetime.datetime):
        index = self._localize_date(time)
        return self._data[index]

    def get_value_mask(self, value) -> np.ndarray:
        return self._data == value

    def get_masked_values(self, mask) -> np.ndarray:
        return self._data[mask]
