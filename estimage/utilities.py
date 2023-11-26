import cProfile
import functools
import typing

import numpy as np
import scipy as sp


def first_nonzero_index_of(values):
    if not np.any(values != 0):
        raise ValueError("Array is identical to zero")
    for index, value in enumerate(values):
        if value != 0:
            return index


def last_nonzero_index_of(values):
    if not np.any(values != 0):
        raise ValueError("Array is identical to zero")
    for index, value in enumerate(values[::-1]):
        if value != 0:
            return len(values) - 1 - index


def profile(wrapped):
    """
    Decorate a function to save profiling info to the working directory.
    The order of decorators matters.
    """
    @functools.wraps(wrapped)
    def wrapper(* args, ** kwargs):
        with cProfile.Profile() as pr:
            ret = wrapped(* args, ** kwargs)
            pr.dump_stats(f"{wrapped.__name__}.pstats")
        return ret
    return wrapper


def _container_in_one_of(reference: typing.Container, sets: typing.Iterable[typing.Container]):
    for candidate in sets:
        if reference in candidate:
            return True
    return False


def reduce_subsets_from_sets(sets: typing.Iterable[typing.Container]):
    """
    Given a sequence of containers, return a reduced sequence of containers
    where no element is contained in other elements
    """
    reduced = []
    for index, evaluated in enumerate(sets):
        if _container_in_one_of(evaluated, sets[index + 1:]):
            continue
        if _container_in_one_of(evaluated, reduced):
            continue
        reduced.append(evaluated)
    return reduced


def norm_pdf(values, dx):
    norming_factor = values.sum() * dx
    if norming_factor:
        values[:] /= norming_factor


def _trim_dom_hom(dom, hom):
    starting_index = first_nonzero_index_of(hom)
    ending_index = last_nonzero_index_of(hom)
    sl = slice(starting_index, ending_index + 1)
    return dom[sl], hom[sl]


def eco_convolve(dom1, hom1, dom2, hom2):
    dom1, hom1 = _trim_dom_hom(dom1, hom1)
    dom2, hom2 = _trim_dom_hom(dom2, hom2)
    hom = np.convolve(hom1, hom2)
    dom = np.linspace(
        dom1[0] + dom2[0],
        dom1[-1] + dom2[-1],
        len(hom)
    )
    return dom, hom


def interpolate_to_length(dom, hom, length):
    interp = sp.interpolate.interp1d(dom, hom)
    dom = np.linspace(dom[0], dom[-1], length)
    hom = interp(dom)
    return dom, hom


def extent_index(array, ratio):
    extent = array.max() - array.min()
    actual_ratio = array.min() + extent * ratio / 100.0
    search_array = np.abs(array - actual_ratio)
    return np.argmin(search_array)
