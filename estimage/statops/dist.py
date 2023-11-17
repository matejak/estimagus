import numpy as np
import scipy as sp

from . import func


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

    def _get_cdf_bounds(self, pdf_bounds):
        start = max(0, pdf_bounds.start - 1)
        stop = min(self.dom.size, pdf_bounds.stop + 1)
        cdf_bounds = slice(start, stop)
        return cdf_bounds

    def get_dist(self):
        pdf_fun = sp.interpolate.interp1d(
            self.dom, self.cached_pdf, fill_value=0, bounds_error=False)
        cdf_fun = sp.interpolate.interp1d(
            self.dom, self.cached_cdf, fill_value=(0, 1), bounds_error=False)
        pdf_bounds = func.get_pdf_bounds_slice(self.cached_pdf)
        cdf_bounds = self._get_cdf_bounds(pdf_bounds)
        ppf_fun = sp.interpolate.interp1d(
            self.cached_cdf[cdf_bounds], self.dom[cdf_bounds])
        return self._get_randvar(pdf_fun, cdf_fun, ppf_fun)(a=self.a, b=self.b)

    def _get_randvar(self, pdf_fun, cdf_fun, ppf_fun):
        class randvar(sp.stats.rv_continuous):

            def _pdf(s, x):
                return pdf_fun(x)

            def _cdf(s, x):
                return cdf_fun(x)

            def _ppf(s, x):
                return ppf_fun(x)
        return randvar

    def get_inverse(self):
        pdf_bounds = func.get_pdf_bounds_slice(self.cached_pdf)
        cdf_bounds = self._get_cdf_bounds(pdf_bounds)
        inverse_cached_cdf = 1 - self.cached_cdf[cdf_bounds]
        inverse_dom = 1.0 / self.dom[cdf_bounds]

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

        return self._get_randvar(pdf_fun, cdf_fun, ppf_fun)(a=new_a, b=new_b)


def get_lognorm_given_mean_median(mean, median, samples=200):
    dom = np.linspace(0, 1, samples)
    better_spaced_dom = dom ** 1.8 * mean * 20
    mu, sigma = func.get_lognorm_mu_sigma(mean, median)
    hom = func.lognorm_pdf(better_spaced_dom, mu, sigma)
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
        if estimate.expected == 0:
            completion_dist = sp.stats.norm(loc=0, scale=0)
        else:
            completion_dist = Dist(dom0 / estimate.expected, hom0).get_inverse()
    else:
        dom_e, hom_e = estimate.get_pert(samples)
        dom_v, hom_v = get_defining_pdf_chunk(inverse_dist, samples)
        dom, hom = func.multiply_two_pdfs(dom_v, hom_v, dom_e, hom_e)
        completion_dist = Dist(dom, hom).get_dist()
    return completion_dist
