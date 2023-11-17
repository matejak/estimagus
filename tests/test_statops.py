import numpy as np
import scipy as sp
import pytest

from estimage import statops as tm
from estimage.statops import dist, func
from estimage import data


class InspectedDist(tm.dist.Dist):
    def get_pdf_first_moment(self):
        fun = self.dom * self.cached_pdf
        fun = sp.interpolate.interp1d(self.dom, self.dom * self.cached_pdf)
        first_moment, _ = sp.integrate.quad(fun, self.a, self.b, limit=200)
        return first_moment


def test_calculation_of_trivial_distribution():
    value = 4
    dom = np.arange(11)
    hom = np.zeros_like(dom, float)
    hom[value] = 1
    distmaker = InspectedDist(dom, hom)

    assert distmaker.get_pdf_first_moment() == pytest.approx(value, rel=1e-2)
    assert distmaker.cached_cdf[-1] == 1
    assert distmaker.cached_cdf[0] == 0
    assert distmaker.cached_cdf.min() == 0
    assert distmaker.cached_cdf.max() == pytest.approx(1)


def test_rvs_of_trivial_pdf():
    np.random.seed(813456)
    value = 4
    dom = np.arange(11)
    hom = np.zeros_like(dom, float)
    hom[value] = 1
    distmaker = tm.dist.Dist(dom, hom)
    distro = distmaker.get_dist()
    assert distro.ppf(0.99) - distro.ppf(0.01) > 1.5
    values = distro.rvs(size=200)
    assert values.mean() == pytest.approx(value, abs=0.05)


def test_rvs_of_inverse_unpadded_pdf():
    np.random.seed(213457)
    dom = np.linspace(5, 10, 20)
    hom = np.ones_like(dom, float)
    sample_size = 50

    distmaker = tm.dist.Dist(dom, hom)
    distro = distmaker.get_dist()
    points = distro.rvs(size=sample_size)
    inverted_points = 1.0 / points

    inverse_dist = distmaker.get_inverse()
    inverse_points = inverse_dist.rvs(size=sample_size)

    assert sp.stats.kstest(inverse_points, inverted_points).pvalue > 0.10


def test_rvs_of_inverse_gauss_pdf():
    np.random.seed(213457)
    gauss_mean = 1.35
    gauss_std = 0.4
    dom_len = 80

    gauss_dom = np.linspace(gauss_mean - gauss_std * 3.2, gauss_mean + gauss_std * 3.2, dom_len)
    distmaker = dist.Dist(gauss_dom, sp.stats.norm.pdf(gauss_dom, loc=gauss_mean, scale=gauss_std))
    distro = distmaker.get_dist()

    sample_size = 50

    points = distro.rvs(size=sample_size)
    inverted_points = 1.0 / points

    inverse_dist = distmaker.get_inverse()
    inverse_points = inverse_dist.rvs(size=sample_size)

    assert sp.stats.kstest(inverse_points, inverted_points).pvalue > 0.10


def test_rvs_of_inverse_pdf():
    np.random.seed(213457)
    dom = np.arange(11)
    hom = np.zeros_like(dom, float)
    hom[4:6] = 1
    sample_size = 50

    distmaker = tm.dist.Dist(dom, hom)
    distro = distmaker.get_dist()
    points = distro.rvs(size=sample_size)
    inverted_points = 1.0 / points

    inverse_dist = distmaker.get_inverse()
    inverse_points = inverse_dist.rvs(size=sample_size)

    assert sp.stats.kstest(inverse_points, inverted_points).pvalue > 0.10


def test_multiplication_of_trivial_pdfs():
    np.random.seed(213456)
    dom = np.linspace(0, 4, 41)
    value = 3

    sample_size = 50
    hom1 = np.zeros_like(dom, float)
    hom1[1 * 10] = 1
    distmaker = tm.dist.Dist(dom, hom1)
    rvs1 = distmaker.get_dist().rvs(size=sample_size)

    hom2 = np.zeros_like(dom, float)
    hom2[value * 10] = 1
    distmaker = tm.dist.Dist(dom, hom2)
    rvs2 = distmaker.get_dist().rvs(size=sample_size)

    dom, hom = tm.func.multiply_two_pdfs(dom, hom1, dom, hom2)
    distmaker = tm.dist.Dist(dom, hom)
    distro = distmaker.get_dist()
    values = distro.rvs(size=sample_size)
    assert sp.stats.kstest(values, rvs1 * rvs2).pvalue > 0.10


def test_multiplication_of_disproportionate_pdfs():
    dom = np.linspace(0, 4, 41)

    sample_size = 50
    hom1 = np.zeros_like(dom, float)
    hom1[30] = 1
    distmaker = tm.dist.Dist(dom, hom1)
    rvs1 = distmaker.get_dist().rvs(size=sample_size)

    hom2 = np.zeros_like(dom, float)
    hom2[40] = 1
    distmaker = tm.dist.Dist(dom, hom2)
    rvs2 = distmaker.get_dist().rvs(size=sample_size)

    dom, hom = tm.func.multiply_two_pdfs(dom, hom1, dom, hom2)
    distmaker = tm.dist.Dist(dom, hom)
    distro = distmaker.get_dist()
    values = distro.rvs(size=sample_size)
    assert sp.stats.kstest(values, rvs1 * rvs2).pvalue > 0.10


def test_lognorm_fit():
    mean = 2.6
    median = 2
    distro = tm.dist.get_lognorm_given_mean_median(mean, median)
    assert distro.mean() == pytest.approx(mean, rel=1e-2)
    assert distro.median() == pytest.approx(median, rel=1e-2)

    mean = 1.2
    median = 0.8
    distro = tm.dist.get_lognorm_given_mean_median(mean, median)
    assert distro.mean() == pytest.approx(mean, rel=1e-2)
    assert distro.median() == pytest.approx(median, rel=1e-2)


def test_getting_pdf_chunk():
    distro = sp.stats.uniform(0, 1)
    samples = 100
    dom, hom = tm.dist.get_defining_pdf_chunk(distro, samples)
    assert len(dom) == samples
    assert hom[0] == 0
    assert hom[-1] == 0
    assert distro.cdf(dom[-2]) - distro.cdf(dom[1]) > 0.95
    inner_dom = dom[1:-1]
    np.testing.assert_array_equal(distro.pdf(inner_dom), hom[1:-1])


def test_estimate_divided_by_lognorm():
    np.random.seed(213457)
    samples = 100
    velocity_mean = 2
    velocity_fit = tm.dist.get_lognorm_given_mean_median(velocity_mean, 1.5)

    estimate = data.Estimate.from_triple(4, 4, 4)
    completion_dist = tm.dist.divide_estimate_by_mean_median_fit(estimate, velocity_mean, 1.5, samples)
    forecast = completion_dist.rvs(size=samples * 10)
    experiment = 4 / velocity_fit.rvs(size=samples * 10)
    assert sp.stats.kstest(forecast, experiment).pvalue > 0.10

    estimate = data.Estimate.from_triple(5, 4, 9)
    completion_dist = tm.dist.divide_estimate_by_mean_median_fit(estimate, velocity_mean, 1.5, samples)
    forecast = completion_dist.rvs(size=samples * 10)
    experiment = estimate.pert_rvs(samples * 10) / velocity_fit.rvs(size=samples * 10)
    assert sp.stats.kstest(forecast, experiment).pvalue > 0.10

    estimate = data.Estimate.from_triple(0, 0, 0)
    completion_dist = tm.dist.divide_estimate_by_mean_median_fit(estimate, velocity_mean, 1.5, samples)
    forecast = completion_dist.rvs(size=samples * 10)
    assert forecast.max() < 0.1


@pytest.fixture
def degenerate_velocity():
    velocity_dom = np.array([2])
    velocity_hom = np.array([1])
    return velocity_dom, velocity_hom


def test_trivial_completion(degenerate_velocity):
    velocity_dom, velocity_hom = degenerate_velocity

    completed_dom, completed_hom = tm.func.get_completion_pdf(velocity_dom, velocity_hom, 0)
    assert len(completed_dom) == 1
    assert completed_dom[0] == 0
    assert completed_hom[0] == 1

    completed_dom, completed_hom = tm.func.get_completion_pdf(velocity_dom, velocity_hom, 1)
    assert len(completed_dom) == 1
    assert completed_dom[0] == 2
    assert completed_hom[0] == 1


@pytest.fixture
def quasireal_velocity():
    velocity_dom = np.arange(5) + 1
    velocity_hom = np.zeros(5)
    sl = slice(1, 4)
    velocity_hom[sl] = 1 / 3.0
    return velocity_dom, velocity_hom


def test_quasireal_completion(quasireal_velocity):
    velocity_dom, velocity_hom = quasireal_velocity
    sl = velocity_hom > 0

    completed_dom, completed_hom = tm.func.get_completion_pdf(velocity_dom, velocity_hom, 0)
    assert len(completed_dom) == 1
    assert completed_dom[0] == 0
    assert completed_hom[0] == 1

    completed_dom, completed_hom = tm.func.get_completion_pdf(velocity_dom, velocity_hom, 1)
    np.testing.assert_array_almost_equal(completed_dom, velocity_dom[sl])
    np.testing.assert_array_almost_equal(completed_hom, velocity_hom[sl])

    completed_dom, completed_hom = tm.func.get_completion_pdf(velocity_dom, velocity_hom, 10)
    assert completed_hom.sum() == pytest.approx(1)
    assert completed_dom[np.argmax(completed_hom)] == 10 * velocity_dom[2]
    assert completed_hom.min() >= 0
    assert completed_dom[0] <= 10 * velocity_dom[sl][0]
    assert completed_dom[-1] >= 10 * velocity_dom[sl][-1]


def test_evaluation(degenerate_velocity, quasireal_velocity):
    assert tm.func.evaluate_completion_pdf(* degenerate_velocity, 2.1) == 0
    assert tm.func.evaluate_completion_pdf(* degenerate_velocity, 1.9) == 1
    assert tm.func.evaluate_completion_pdf(* quasireal_velocity, 4.5) == 0
    assert tm.func.evaluate_completion_pdf(* quasireal_velocity, 3.5) == 1 / 3.0
    assert tm.func.evaluate_completion_pdf(* quasireal_velocity, 2.5) == 2 / 3.0


def test_construct_evaluation(quasireal_velocity):
    distfun = tm.func.construct_evaluation(* quasireal_velocity, 0)
    assert distfun.size == 1
    assert distfun[0] == 1

    distfun = tm.func.construct_evaluation(* quasireal_velocity, 0.1)
    assert distfun.size == 2
    assert distfun[-1] == 1

    distfun = tm.func.construct_evaluation(* quasireal_velocity, 3.9)
    assert distfun.size == 3
    assert distfun[-1] == pytest.approx(1)

    distfun = tm.func.construct_evaluation(* quasireal_velocity, 4)
    assert distfun.size == 4
    assert distfun[-1] == pytest.approx(1)

    distfun = tm.func.construct_evaluation(* quasireal_velocity, 4, 3)
    assert distfun.size == 3
    assert distfun[-1] < 1


def test_separate_array():
    testa = np.array([1])
    assert tm.func.separate_array_into_good_and_bad(testa, 2)[0][0] == 1
    assert tm.func.separate_array_into_good_and_bad(testa, 2)[1].size == 0

    assert tm.func.separate_array_into_good_and_bad(testa, 1)[1][0] == 1
    assert tm.func.separate_array_into_good_and_bad(testa, 1)[0].size == 0

    testa = np.array([1, 2, 500])
    assert tm.func.separate_array_into_good_and_bad(testa, 2)[1][0] == 500
    assert tm.func.separate_array_into_good_and_bad(testa, -1)[1].size == 0


def test_mean_median_without_outliers():
    np.random.seed(213451)
    mean = 1.2
    median = 1.0
    lognorm = tm.dist.get_lognorm_given_mean_median(mean, median)
    points = lognorm.rvs(size=10000)
    bad_points = points.copy()
    bad_points[-800:] = 0
    bad_points[-801] = points[-801:].sum()
    assert points.sum() == pytest.approx(bad_points.sum())
    meh_mean, meh_median = tm.func.get_mean_median_dissolving_outliers(bad_points, 10)
    assert mean == pytest.approx(meh_mean, rel=1e-2)
    real_bad_median = np.median(bad_points)
    assert real_bad_median < meh_median
    assert median < meh_median
    assert median == pytest.approx(meh_median, rel=5e-1)


def test_lognorm_ops():
    mu = -0.5
    sigma = 0.8
    mean = np.exp(mu + sigma ** 2 / 2.0)
    variance = tm.func.get_lognorm_variance(mu, sigma)
    new_mu, new_sigma = tm.func.get_lognorm_mu_sigma_from_lognorm_mean_variance(mean, variance)
    assert mu == pytest.approx(new_mu)
    assert sigma == pytest.approx(new_sigma)
