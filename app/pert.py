import scipy as sp
import numpy as np

import matplotlib.pyplot as plt


class Pert:
    def __init__(self, opt, real, pes):
        self.opt = opt
        self.real = real
        self.pes = pes

    @property
    def beta_a(self):
        return 1 + 4 * (self.real - self.opt) / self.width

    @property
    def beta_b(self):
        return 1 + 4 * (self.pes - self.real) / self.width

    @property
    def width(self):
        return self.pes - self.opt

    @property
    def expected(self):
        return (self.opt + self.pes + 4 * self.real) / 6.0


def norm_prob_function(dom, values_array):
    values_array /= values_array.sum() * (dom[1] - dom[0])


def get_quantile_boundaries(dom, values, boundary_quantile=0.01):
    left_boundary = dom[find_arg_quantile(values, boundary_quantile)]
    right_boundary = dom[find_arg_quantile(values, 1 - boundary_quantile)]
    print(f"{left_boundary=} {right_boundary=}")


def find_quantile_with_filtering(dom, values, quantile, threshold_quantile=0.02):
    left_threshold = values[find_arg_quantile(values, threshold_quantile)]
    right_threshold = values[find_arg_quantile(values, 1 - threshold_quantile)]
    threshold = (left_threshold + right_threshold) / 2.0
    print(f"{left_threshold=} {right_threshold=}")
    filtered_values = values.copy()
    filtered_values[values < threshold] = 0
    index = find_arg_quantile(filtered_values, quantile)
    return dom[index]


def find_quantile(dom, values, quantile):
    index = find_arg_quantile(values, quantile)
    return dom[index]


def find_center_of_gravity(dom, values):
    contributions = dom * values
    imbalance = contributions.sum() / values.sum()
    return imbalance


def find_arg_quantile(values, quantile):
    distfun = np.cumsum(values)
    distfun /= distfun[-1]
    distance_from_quantile = np.abs(distfun - quantile)
    index = np.argmin(distance_from_quantile)
    return index


def plot_composed_perts():
    fig, ax = plt.subplots(1, 1)
    pert = Pert(2, 4, 10)

    basesize = 500
    dom = np.linspace(0, 12, basesize)
    values = sp.stats.beta.pdf(dom, pert.beta_a, pert.beta_b, scale=pert.width, loc=pert.opt)
    plot_beta(ax, dom, values, pert.expected)

    double_pert = np.convolve(values, values)
    dom_double_pert = np.linspace(0, 24, basesize * 2 - 1)
    norm_prob_function(dom_double_pert, double_pert)
    plot_beta(ax, dom_double_pert, double_pert, pert.expected * 2)

    triple_pert = np.convolve(double_pert, values)
    dom_triple_pert = np.linspace(0, 36, basesize * 3 - 2)
    norm_prob_function(dom_triple_pert, triple_pert)
    plot_beta(ax, dom_triple_pert, triple_pert, pert.expected * 3)

    quad_pert = np.convolve(double_pert, double_pert)
    dom_quad_pert = np.linspace(0, 48, basesize * 4 - 3)
    norm_prob_function(dom_quad_pert, quad_pert)
    plot_beta(ax, dom_quad_pert, quad_pert, pert.expected * 4)

    ax.grid()
    ax.legend()

    plt.show()


def plot_beta(ax, dom, values, expected):
    ax.plot(dom, values, 'b-', lw=2, alpha=0.6, label='beta')
    ax.axvline(expected, color="orange")
    # stats_expected = find_quantile(dom, values, 0.5)
    stats_expected = find_center_of_gravity(dom, values)
    ax.axvline(stats_expected, color="green")
    print(f"diff of estimates: {expected - stats_expected}")
    get_quantile_boundaries(dom, values)

