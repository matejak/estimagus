import numpy as np
import scipy as sp


# \int_{-\inf}^{\inf}l(x)\int_{x}^{\inf}g(t)\, \textup{d}t\, \textup{d}x
# where l is the function that we think should be lower, and g the greater
def _integrate(dom, one, two):
    res = 0
    for i, x in enumerate(dom):
        toadd = two[i] * 0.5
        toadd += sum(two[i + 1:])
        toadd *= one[i]
        res += toadd
    return res


def _integrate_estimate_both_degenerate(one, two):
    if one.expected == two.expected:
        return 0.5
    if one.expected < two.expected:
        return 1
    return 0


def _integrate_estimate_second_degenerate(one, two):
    threshold = two.expected
    rv = one._get_rv()
    return rv.cdf(threshold)


def _integrate_estimate_first_degenerate(one, two):
    threshold = one.expected
    rv = two._get_rv()
    return 1 - rv.cdf(threshold)


INTEGRATION_PRECISION = 0.001


# \int_{-\inf}^{\inf}l(x)\int_{x}^{\inf}g(t)\, \textup{d}t\, \textup{d}x is in fact
# \int_{-\inf}^{\inf}l(x)\, \textup{d}x - \int_{-\inf}^{\inf}l(x)G(x)\, \textup{d}x =
# = 1 - \int_{-\inf}^{\inf}l(x)G(x)\, \textup{d}x where
# G(x) is distribution function of the g randvar
def _integrate_estimate(one, two):
    # unlike upper bound case, PDF and CDF are zero below their respective lower bound
    effective_lower_bound = max(one.source.optimistic, two.source.optimistic)
    safe_upper_bound = max(one.source.pessimistic, two.source.pessimistic)
    lower_rv = one._get_rv()
    upper_rv = two._get_rv()
    def integrand(x): return lower_rv.pdf(x) * upper_rv.cdf(x)
    result = sp.integrate.quad(integrand, effective_lower_bound, safe_upper_bound, epsabs=INTEGRATION_PRECISION)
    return 1 - result[0]


def is_lower(dom, one, two):
    dom = np.array(dom, dtype=float)
    one = np.array(one, dtype=float)
    one /= one.sum()
    two = np.array(two, dtype=float)
    two /= two.sum()
    return _integrate(dom, one, two)


def estimate_is_lower(one, two):
    if one.sigma == 0 and two.sigma == 0:
        return _integrate_estimate_both_degenerate(one, two)
    if two.sigma == 0:
        return _integrate_estimate_second_degenerate(one, two)
    if one.sigma == 0:
        return _integrate_estimate_first_degenerate(one, two)
    return _integrate_estimate(one, two)
