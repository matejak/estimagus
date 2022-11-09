import math

import numpy as np

from .entities.target import BaseTarget
from .entities.estimate import Estimate, EstimInput
from .entities.task import TaskModel, MemoryTaskModel
from .entities.composition import Composition, MemoryComposition
from .entities.pollster import Pollster, MemoryPollster
from .entities.model import EstiModel


def find_arg_quantile(values, quantile):
    distfun = np.cumsum(values)
    distfun /= distfun[-1]
    distance_from_quantile = np.abs(distfun - quantile)
    index = np.argmin(distance_from_quantile)
    return index


def sink_pert(values, amount):
    new_values = values - amount
    new_values[new_values < 0] = 0
    return new_values


def pert_compute_expected_value(dom, values):
    contributions = dom * values
    imbalance = contributions.sum() / values.sum()
    return imbalance


def compute_estimation_from_pert_optimize(dom, values, expected, sigma):
    corresponding_input = pert_to_naive_estiminput(dom, values)
    x0 = (corresponding_input.optimistic, corresponding_input.most_likely, corresponding_input.pessimistic)
    x0 = (corresponding_input.optimistic, corresponding_input.pessimistic)
    corr_estim = Estimate.from_input(corresponding_input)

    pert = corr_estim.get_pert(dom=dom)
    pert_autocorr = np.correlate(pert[1], pert[1])

    def objective_function(omp):
        omp = [omp[0], corresponding_input.most_likely, omp[1]]
        expected_component = (omp[0] + omp[1] * 4 + omp[2]) / 6.0 - expected
        sigma1_component = math.sqrt((omp[1] - omp[0]) * (omp[2]- omp[1]) / 7.0) - sigma
        sigma2_component = (omp[2] - omp[0]) / 6.0 - sigma
        sigma_component = sigma1_component**2 * (1 - SIGMA_LAMBDA) + sigma2_component**2 * SIGMA_LAMBDA
        pert2 = Estimate.from_triple(omp[1], omp[0], omp[2]).get_pert(dom=dom)
        perts_corr = np.correlate(pert[1], pert2[1])
        divergence_component = (
            (1 - pert_autocorr / perts_corr)**2 * 1e1
            + (omp[1] - corresponding_input.most_likely) ** 2 * 0.05)
        ret = expected_component**2 * 4 + sigma_component * 1  + divergence_component
        return ret

    import scipy.optimize
    result = scipy.optimize.minimize(
        objective_function, x0,
        # method='Nelder-Mead',
        method='Powell',
        # method='COBYLA',
        bounds=[
            (x0[0], (x0[0] + corresponding_input.most_likely) / 2.0),
            ((x0[1] + corresponding_input.most_likely) / 2.0, x0[1])],
        )
    print(result)
    resulting_input = EstimInput(corresponding_input.most_likely)
    resulting_input.optimistic = result.x[0]
    resulting_input.pessimistic = result.x[1]
    ret = Estimate.from_input(resulting_input)
    print(f"expected: {expected=}, {sigma=}")
    print(f"before: {corr_estim.source}, after: {resulting_input}")
    print(f"before: {corr_estim.expected} {corr_estim.sigma}, after: {ret.expected} {ret.sigma}")
    return ret


def sink_pert_to_get_expected_value(dom, values, expected_target):
    import scipy.optimize

    current_value = pert_compute_expected_value(dom, values)
    initial_sink = values.max() * (1 - current_value / expected_target) / 20.0
    # print(f"{initial_sink=}")

    print(f"{expected_target=}")
    def objective_function(sink):
        working_values = values.copy()
        working_values = sink_pert(working_values, sink)
        # current_value = pert_compute_expected_value(dom, working_values)

        corresponding_input = pert_to_naive_estiminput(dom, working_values)
        corresponding_expected = Estimate.from_input(corresponding_input).expected
        # print(f"{corresponding_expected=} {abs(corresponding_expected - expected_target)}")
        # return abs(current_value - expected_target) + abs(corresponding_expected - expected_target)
        ret = abs(corresponding_expected - expected_target)
        print(f"{sink=} -> {corresponding_expected=}")
        return ret

    result = scipy.optimize.minimize(
        objective_function, initial_sink,
        method='Nelder-Mead',
        # method='B'GS,
        bounds=[(0, initial_sink)],
        )
    print(result)
    values[:] = sink_pert(values, result.x)
    print (f"before: {objective_function(0)}, after: {objective_function(result.x)}")
