import cProfile
import functools
import typing


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


def get_random_variable(dom, values):
    import numpy as np
    import scipy as sp

    class Rv(sp.stats.rv_continuous):
        def __init__(self, * args, ** kwargs):
            super().__init__(* args, ** kwargs)
            self.a = dom[0]
            self.b = dom[-1]

            self._pdf = sp.interpolate.interp1d(dom, values, kind="linear", bounds_error=False, fill_value=0)
            self._cdf = sp.interpolate.interp1d(dom, np.cumsum(values) / sum(values), kind="linear")
            self._ppf = sp.interpolate.interp1d(np.cumsum(values) / sum(values), dom, kind="linear")

    return Rv()(loc=0, scale=1)
