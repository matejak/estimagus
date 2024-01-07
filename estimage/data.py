import math

import numpy as np

from .entities.card import BaseCard
from .entities.status import Statuses
from .entities.estimate import Estimate, EstimInput
from .entities.task import TaskModel, MemoryTaskModel
from .entities.composition import Composition, MemoryComposition
from .entities.pollster import Pollster
from .entities.model import EstiModel
from .entities.event import Event, EventManager


def pert_compute_expected_value(dom, values):
    contributions = dom * values
    imbalance = contributions.sum() / values.sum()
    return imbalance
