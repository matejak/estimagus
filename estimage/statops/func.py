import numpy as np
import scipy as sp

from .. import utilities


def get_pdf_bounds_slice(sampled_pdf):
    first = utilities.first_nonzero_index_of(sampled_pdf)
    last_inclusive = utilities.last_nonzero_index_of(sampled_pdf)
    return slice(first, last_inclusive + 1)


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


def evaluate_completion_pdf(completion_dom, completion_hom, remaining):
    ratio = completion_hom[completion_dom > remaining].sum()
    return ratio / completion_hom.sum()


def construct_evaluation(velocity_dom, velocity_hom, todo, iter_limit=100):
    if todo == 0:
        return np.ones(1)
    res_dom = np.zeros(1)
    res_hom = np.ones(1)
    results = []
    for _ in range(iter_limit):
        result = evaluate_completion_pdf(res_dom, res_hom, todo)
        results.append(result)
        if result > 0.99:
            break
        res_dom, res_hom = utilities.eco_convolve(velocity_dom, velocity_hom, res_dom, res_hom)
        # TODO: What is the cause of this instability? Where is the best place to norm?
        res_hom /= res_hom.sum()
        res_hom[res_hom < res_hom.max() * 1e-4] = 0
    return np.array(results)


def lognorm_pdf(dom, mu, sigma):
    dist = sp.stats.lognorm(s=sigma, scale=np.exp(mu))
    return dist.pdf(dom)


def get_lognorm_mu_sigma(mean, median):
    mu = np.log(median)
    sigma = np.sqrt(2 * (np.log(mean) - mu))
    return mu, sigma


def separate_array_into_good_and_bad(wild_array, outlier_threshold):
    if outlier_threshold == -1:
        return wild_array, np.array([])
    raw_mean = wild_array.mean()
    good_array = wild_array[wild_array < raw_mean * outlier_threshold]
    bad_array = wild_array[wild_array >= raw_mean * outlier_threshold]
    return good_array, bad_array


def get_mean_median_dissolving_outliers(wild_array, outlier_threshold=-1):
    raw_mean = wild_array.mean()
    good_array, _ = separate_array_into_good_and_bad(wild_array, outlier_threshold)
    low_mean = good_array.mean()
    low_median = np.median(good_array)
    return raw_mean, low_median * raw_mean / low_mean


def _minimize_pdf_dom_hom(dom, hom):
    bounds = get_pdf_bounds_slice(hom)
    start = max(0, bounds.start - 1)
    stop = min(dom.size, bounds.stop + 1)
    larger_bounds = slice(start, stop)
    return dom[larger_bounds], hom[larger_bounds]


class PdfMultiplicator:
    def __init__(self, dom1, hom1, dom2, hom2):
        dom1, hom1 = _minimize_pdf_dom_hom(dom1, hom1)
        dom2, hom2 = _minimize_pdf_dom_hom(dom2, hom2)

        result_bounds = (dom1[0] * dom2[0], dom1[-1] * dom2[-1])

        self.dom = np.linspace(result_bounds[0], result_bounds[1], len(hom1) + len(hom2))

        self.values = np.zeros_like(self.dom, float)
        self.interp_1 = sp.interpolate.interp1d(dom1, hom1, fill_value=0, bounds_error=False)
        self.interp_2 = sp.interpolate.interp1d(dom2, hom2, fill_value=0, bounds_error=False)

        self.dom1 = dom1

    # see also https://en.wikipedia.org/wiki/Distribution_of_the_product_of_two_random_variables
    # Int pdf1(t) pdf2(x / t) / abs(t) dt
    def integrand(self, t, x):
        body = self.interp_1(t)
        if body == 0:
            return 0
        body *= self.interp_2(x / t)
        if body == 0:
            return 0
        ret = body / abs(t)
        return ret

    def __call__(self):
        for i, x in enumerate(self.dom):
            a = self.dom1[0]
            b = self.dom1[-1]
            if a == b:
                val = self.integrand(a, x)
            else:
                val = sp.integrate.quad(self.integrand, a, b, args=(x,), limit=20)[0]
            self.values[i] = val

        return self.dom, self.values


# see also https://en.wikipedia.org/wiki/Distribution_of_the_product_of_two_random_variables
# Integral over support of the first pdf
# product(x) = Int pdf1(t) pdf2(x / t) / abs(t) dt
def multiply_two_pdfs(dom1, hom1, dom2, hom2):
    multiplicator = PdfMultiplicator(dom1, hom1, dom2, hom2)
    return multiplicator()
