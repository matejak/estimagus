import datetime

import numpy as np

from ..entities import card

from .timeline import Timeline
from .progress import Progress
from .aggregation import Aggregation, Summary

from .progress import days_between


def get_period(start: datetime.datetime, end: datetime.datetime):
    period = end - start
    return np.zeros(period.days)
