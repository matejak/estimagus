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


def _integrate(dom, one, two):
    res = 0
    for i, x in enumerate(dom):
        toadd = two[i] * 0.5
        toadd += sum(two[i + 1:])
        toadd *= one[i]
        res += toadd
    return res


def is_lower(dom, one, two):
    dom = np.array(dom, dtype=float)
    one = np.array(one, dtype=float)
    one /= one.sum()
    two = np.array(two, dtype=float)
    two /= two.sum()
    return integrate(dom, one, two)

