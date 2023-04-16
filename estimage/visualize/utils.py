import typing
import datetime

import numpy as np


ONE_DAY = datetime.timedelta(days=1)


def get_standard_pyplot():
    import matplotlib.pyplot as plt
    plt.rcParams['svg.fonttype'] = 'none'
    plt.rcParams['font.sans-serif'] = (
        "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Noto Sans", "Liberation Sans",
        "Arial,sans-serif" ,"Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji",
    )
    plt.rcParams['font.size'] = 12
    return plt


def x_axis_weeks_and_months(ax, start, end):
    ticks = dict()
    set_week_ticks_to_mondays(ticks, start, end)
    set_ticks_to_months(ticks, start, end)

    ax.set_xticks(list(ticks.keys()))
    ax.set_xticklabels(list(ticks.values()), rotation=60)

    ax.set_xlabel("time / weeks")


def set_week_ticks_to_mondays(ticks, start, end):
    week_index = 0
    if start.weekday != 0:
        week_index = 1
    for day in range((end - start).days):
        if (start + day * ONE_DAY).weekday() == 0:
            ticks[day] = str(week_index)
            week_index += 1


def set_ticks_to_months(ticks, start, end):
    for day in range((end - start).days):
        if (the_day := (start + day * ONE_DAY)).day == 1:
            ticks[day] = datetime.date.strftime(the_day, "%b")


def insert_element_into_array_after(array: np.ndarray, index: int, value: typing.Any):
    separindex = index + 1
    components = (array[:separindex], np.array([value]), array[separindex:])
    return np.concatenate(components, 0)


def simplify_timeline_array(array_to_simplify):
    if len(array_to_simplify) < 3:
        return array_to_simplify
    simplified = [array_to_simplify[0]]
    for first, middle, last in zip(array_to_simplify[:-2], array_to_simplify[1:-1], array_to_simplify[2:]):
        if np.all(first[1:] == middle[1:]) * np.all(middle[1:] == last[1:]):
            continue
        simplified.append(middle)
    simplified.append(array_to_simplify[-1])
    return np.array(simplified, dtype=array_to_simplify.dtype)
