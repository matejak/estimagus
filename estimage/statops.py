import datetime

import numpy as np
import scipy as sp

from .history import Summary, Aggregation
from . import utilities


def get_pdf_bounds_slice(sampled_pdf):
    first = utilities.first_nonzero_index_of(sampled_pdf)
    last_inclusive = utilities.last_nonzero_index_of(sampled_pdf)
    return slice(first, last_inclusive + 1)


class Dist:
    def __init__(self, dom, pdf):
        self.a = dom[0]
        self.b = dom[-1]
        self.dom = np.linspace(self.a, self.b, len(dom) * 4)
        pdf_obj = sp.interpolate.interp1d(dom, pdf, fill_value=0, bounds_error=False)
        self.cached_pdf = pdf_obj(self.dom)

        self.cached_cdf = np.zeros_like(self.dom, float)
        for i, (start, end) in enumerate(zip(self.dom[:-1], self.dom[1:])):
            self.cached_cdf[i + 1] = self.cached_cdf[i]
            self.cached_cdf[i + 1] += sp.integrate.quad(pdf_obj, start, end, limit=20)[0]
        self.cached_cdf /= self.cached_cdf[-1]

    def get_dist(self):
        pdf_fun = sp.interpolate.interp1d(
            self.dom, self.cached_pdf, fill_value=0, bounds_error=False)
        cdf_fun = sp.interpolate.interp1d(
            self.dom, self.cached_cdf, fill_value=(0, 1), bounds_error=False)
        pdf_bounds = get_pdf_bounds_slice(self.cached_pdf)
        ppf_fun = sp.interpolate.interp1d(
            self.cached_cdf[pdf_bounds], self.dom[pdf_bounds])

        class randvar(sp.stats.rv_continuous):

            def _pdf(self, x):
                return pdf_fun(x)

            def _cdf(self, x):
                return cdf_fun(x)

            def _ppf(self, x):
                return ppf_fun(x)
        return randvar(a=self.a, b=self.b)

    def get_inverse(self):
        pdf_bounds = get_pdf_bounds_slice(self.cached_pdf)
        inverse_cached_cdf = 1 - self.cached_cdf[pdf_bounds]
        inverse_dom = 1.0 / self.dom[pdf_bounds]

        new_a = inverse_dom[-1]
        new_b = inverse_dom[0]

        new_dom = np.linspace(new_a, new_b, len(self.dom))

        cdf_fun = sp.interpolate.interp1d(
            inverse_dom, inverse_cached_cdf, fill_value=(0, 1), bounds_error=False)

        computed_cdf = cdf_fun(new_dom)
        computed_pdf = computed_cdf[1:] - computed_cdf[:-1]

        pdf_fun = sp.interpolate.interp1d(
            new_dom[:-1], computed_pdf, fill_value=0, bounds_error=False)

        ppf_fun = sp.interpolate.interp1d(
            computed_cdf, new_dom)

        class randvar(sp.stats.rv_continuous):

            def _pdf(self, x):
                return pdf_fun(x)

            def _cdf(self, x):
                return cdf_fun(x)

            def _ppf(self, x):
                return ppf_fun(x)
        return randvar(a=new_a, b=new_b)


def get_random_var(dom, hom):
    oversampled_dom = np.linspace(dom[0], dom[-1], len(dom) * 4)

    pdf_obj = sp.interpolate.interp1d(dom, hom, fill_value=0, bounds_error=False)
    oversampled_hom = pdf_obj(oversampled_dom)
    pdf_scale = oversampled_hom.sum() * (dom[1] - dom[0])
    pdf_obj = sp.interpolate.interp1d(dom, hom / pdf_scale, fill_value=0, bounds_error=False)

    cached_cdf = np.ones_like(oversampled_dom)
    cached_cdf = np.cumsum(oversampled_hom)
    cached_cdf /= cached_cdf[-1]

    cdf_obj = sp.interpolate.interp1d(oversampled_dom, cached_cdf, fill_value=(0, 1), bounds_error=False)
    ppf_obj = sp.interpolate.interp1d(cached_cdf, oversampled_dom)

    class randvar(sp.stats.rv_continuous):

        def _pdf(self, x):
            return pdf_obj(x)

        def _cdf(self, x):
            return cdf_obj(x)

        def _ppf(self, x):
            return ppf_obj(x)
    return randvar(a=dom[0], b=dom[-1])


def _minimize_pdf_dom_hom(dom, hom):
    bounds = get_pdf_bounds_slice(hom)
    return dom[bounds], hom[bounds]


# see also https://en.wikipedia.org/wiki/Distribution_of_the_product_of_two_random_variables
# Integral over support of the first pdf
# product(x) = Int pdf1(t) pdf2(x / t) / abs(t) dt
def multiply_two_pdfs(dom1, hom1, dom2, hom2):
    dom1, hom1 = _minimize_pdf_dom_hom(dom1, hom1)
    dom2, hom2 = _minimize_pdf_dom_hom(dom2, hom2)

    result_bounds = (dom1[0] * dom2[0], dom1[-1] * dom2[-1])
    dom = np.linspace(result_bounds[0], result_bounds[1], len(hom1) + len(hom2))

    values = np.zeros_like(dom, float)
    interp_1 = sp.interpolate.interp1d(dom1, hom1, fill_value=0, bounds_error=False)
    interp_2 = sp.interpolate.interp1d(dom2, hom2, fill_value=0, bounds_error=False)

    def integrand(t, x):
        body = interp_1(t)
        if body == 0:
            return 0
        body *= interp_2(x / t)
        if body == 0:
            return 0
        ret = body / abs(t)
        return ret

    def vector_integrand(t, x):
        body = interp_1(t)
        mask = body == 0
        body *= interp_2(x / t)
        body[mask] = 0
        mask = body == 0
        ret = body / np.abs(t)
        body[mask] = 0
        return ret

    for i, x in enumerate(dom):
        val = chunked_quad(20, integrand, dom1[0], dom1[-1], args=(x,), limit=50)
        values[i] = val

    return dom, values


def chunked_quad(num_chunks, fun, start, end, ** kwargs):
    result = 0
    dom = np.linspace(start, end, num_chunks + 1)
    for i in range(num_chunks):
        result += sp.integrate.quad(fun, dom[i], dom[i + 1], ** kwargs)[0]
    return result


def lognorm_pdf(dom, mu, sigma):
    res = np.exp(- (np.log(dom) - mu) ** 2 / 2.0 / sigma ** 2)
    res /= dom * sigma * np.sqrt(2 * np.pi)
    res[dom == 0] = 0
    return res


def get_lognorm_mu_sigma(mean, median):
    mu = np.log(median)
    sigma = np.sqrt(2 * (np.log(mean) - mu))
    return mu, sigma


def separate_array_into_good_and_bad(wild_array, outlier_threshold):
    raw_mean = wild_array.mean()
    good_array = wild_array[wild_array < raw_mean * outlier_threshold]
    bad_array = wild_array[wild_array >= raw_mean * outlier_threshold]
    return good_array, bad_array


def get_mean_median_dissolving_outliers(wild_array, outlier_threshold=5):
    raw_mean = wild_array.mean()
    good_array, _ = separate_array_into_good_and_bad(wild_array, outlier_threshold)
    low_mean = good_array.mean()
    low_median = np.median(good_array)
    return raw_mean, low_median * raw_mean / low_mean


def get_lognorm_given_mean_median(mean, median, samples=200):
    dom = np.linspace(0, 1, samples)
    better_spaced_dom = dom ** 1.8 * mean * 20
    mu, sigma = get_lognorm_mu_sigma(mean, median)
    hom = lognorm_pdf(better_spaced_dom, mu, sigma)
    hom[0] = 0
    hom[-1] = 0
    dist = Dist(better_spaced_dom, hom).get_dist()
    return dist


def get_defining_pdf_chunk(dist, samples):
    a = dist.ppf(0.02)
    b = dist.ppf(0.98)
    margin = (b - a) * 2 / samples
    dom = np.linspace(a - margin, b + margin, samples)
    hom = dist.pdf(dom)
    hom[0] = 0
    hom[-1] = 0
    return dom, hom


def divide_estimate_by_mean_median_fit(estimate, mean, median, samples):
    velocity_fit = get_lognorm_given_mean_median(mean, median)
    dom0, hom0 = get_defining_pdf_chunk(velocity_fit, samples)
    inverse_dist = Dist(dom0, hom0).get_inverse()
    if estimate.variance == 0:
        completion_dist = Dist(dom0 / estimate.expected, hom0).get_inverse()
    else:
        dom_e, hom_e = estimate.get_pert(samples)
        dom_v, hom_v = get_defining_pdf_chunk(inverse_dist, samples)
        dom, hom = multiply_two_pdfs(dom_v, hom_v, dom_e, hom_e)
        completion_dist = Dist(dom, hom).get_dist()
    return completion_dist


def get_lognorm_variance(mu, sigma):
    res = np.exp(sigma ** 2) - 1
    res *= np.exp(2 * mu + sigma ** 2)
    return res


def get_lognorm_mu_sigma_from_lognorm_mean_variance(mean, variance):
    # See https://en.wikipedia.org/wiki/Log-normal_distribution, Variance + Mean
    sigma = np.sqrt(np.log(variance / mean ** 2 + 1))
    mu = np.log(mean) - sigma ** 2 / 2.0
    return mu, sigma


def get_completion_pdf(velocity_dom, velocity_hom, numiter):
    res_dom = np.zeros(1)
    res_hom = np.ones(1)
    for _ in range(numiter):
        res_dom, res_hom = utilities.eco_convolve(velocity_dom, velocity_hom, res_dom, res_hom)
    return res_dom, res_hom


def evaluate_completion_pdf(completion_dom, completion_hom, target):
    ratio = completion_hom[completion_dom > target].sum()
    return ratio / completion_hom.sum()


def construct_evaluation(velocity_dom, velocity_hom, target, iter_limit=100):
    if target == 0:
        return np.ones(1)
    res_dom = np.zeros(1)
    res_hom = np.ones(1)
    results = []
    for _ in range(iter_limit):
        result = evaluate_completion_pdf(res_dom, res_hom, target)
        results.append(result)
        if result > 0.99:
            break
        res_dom, res_hom = utilities.eco_convolve(velocity_dom, velocity_hom, res_dom, res_hom)
        res_hom[res_hom < res_hom.max() * 1e-4] = 0
    return np.array(results)


class StatSummary(Summary):
    OUTLIER_THRESHOLD = 3

    def __init__(self, a: Aggregation, cutoff: datetime.datetime, samples: int=200):
        super().__init__(a, cutoff)
        self._samples = samples

        self.completion = (np.inf, np.inf)
        self._projection_summary()

    def _projection_summary(self):
        todo = self.cutoff_todo + self.cutoff_underway

        if self.daily_velocity > 0:
            sl = get_pdf_bounds_slice(self._velocity_array)
            nonzero_daily_velocity = self._velocity_array[sl]

            v_mean, v_median = get_mean_median_dissolving_outliers(nonzero_daily_velocity, self.OUTLIER_THRESHOLD)

            dist = get_lognorm_given_mean_median(v_mean, v_median, self._samples)
            dom = np.linspace(0, v_mean * 10, self._samples)
            velocity_pdf = dist.pdf(dom)

            completion_projection = construct_evaluation(dom, velocity_pdf, todo, 200)
            self.completion = (0, len(completion_projection))
