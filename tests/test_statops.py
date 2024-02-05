import numpy as np
import scipy as sp
import pytest

from estimage import statops as tm
from estimage.statops import func
from estimage import data


def test_lognorm_fit():
    mean = 2.6
    median = 2
    distro = tm.func.get_lognorm_given_mean_median(mean, median)
    assert distro.mean() == pytest.approx(mean, rel=1e-2)
    assert distro.median() == pytest.approx(median, rel=1e-2)

    mean = 1.2
    median = 0.8
    distro = tm.func.get_lognorm_given_mean_median(mean, median)
    assert distro.mean() == pytest.approx(mean, rel=1e-2)
    assert distro.median() == pytest.approx(median, rel=1e-2)


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
    lognorm = tm.func.get_lognorm_given_mean_median(mean, median)
    points = lognorm.rvs(size=10000)
    bad_points = points.copy()
    bad_points[-800:] = 0
    bad_points[-801] = points[-801:].sum()
    assert points.sum() == pytest.approx(bad_points.sum())
    meh_mean, meh_median = tm.func.get_mean_median_dissolving_outliers(bad_points, 10)
    assert mean == pytest.approx(meh_mean, rel=2e-2)
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


def test_eta_of_completion():
    v_mean = 10
    v_stdev = 0
    std_confidence = 0.95
    high__confidence = 0.99
    assert tm.func.get_time_to_completion(v_mean, v_stdev, 0) == 0
    assert tm.func.get_time_to_completion(v_mean, v_stdev, 1) == pytest.approx(0.1)
    assert tm.func.get_time_to_completion(v_mean, v_stdev, 1, 0) == 0

    v_stdev = 2
    dst = 40
    duration = tm.func.get_time_to_completion(v_mean, v_stdev, dst, std_confidence)
    assert duration > dst / v_mean
    assert pytest.approx(dst) == sp.stats.norm(loc=duration * v_mean, scale=v_stdev * np.sqrt(duration)).ppf(1 - std_confidence)
    assert duration < func.get_time_to_completion(v_mean, v_stdev, dst, high__confidence)


def test_prob_of_completion_trivial():
    assert tm.func.get_prob_of_completion(0, 0, 0, 0) == 1
    assert tm.func.get_prob_of_completion(1, 0, 1, 0.9) == 0
    assert tm.func.get_prob_of_completion(1, 0, 1, 1.1) == 1

    np.testing.assert_array_equal(
        tm.func.get_prob_of_completion_vector(1, 0, 0, np.arange(3)),
        np.ones(3))

    np.testing.assert_array_equal(
        tm.func.get_prob_of_completion_vector(1, 0, 1, np.arange(3) * 0.8),
        np.array([0, 0, 1], dtype=float))


def test_prob_of_completion_correspondence():
    assert tm.func.get_prob_of_completion(1, 0.01, 1, 0) == 0
    assert tm.func.get_prob_of_completion(1, 0.01, 1, 0.8) == 0
    assert tm.func.get_prob_of_completion(1, 0.01, 1, 1.1) == 1
    assert tm.func.get_prob_of_completion(1, 0.01, 1, 1) == 0.5

    np.testing.assert_array_equal(
        tm.func.get_prob_of_completion_vector(1, 0.01, 1, np.array([0, 1, 2])),
        np.array([0, 0.5, 1]))


def test_prob_of_completion_variance_reduces_success():
    assert tm.func.get_prob_of_completion(1, 0.1, 1, 1.1) == pytest.approx(0.83, rel=0.01)
    assert tm.func.get_prob_of_completion(1, 0.1, 1, 0.9) == pytest.approx(0.146, rel=0.01)


def _infer_1d_lognorm(mu, sigma, sample_size, rel_error):
    samples = sp.stats.lognorm.rvs(scale=np.exp(mu), s=sigma, size=sample_size)

    est_mu, est_sigma = tm.func.autoestimate_lognorm(samples)

    assert mu == pytest.approx(est_mu, rel=rel_error)
    assert sigma == pytest.approx(est_sigma, rel=rel_error)


def test_infer_1d_lognorm():
    np.random.seed(22)

    _infer_1d_lognorm(2.25, 0.73, 30, 0.1)
    _infer_1d_lognorm(3.25, 0.3, 50, 0.1)
    _infer_1d_lognorm(3.25, 1.2, 50, 0.1)


def test_lognorm_mean_variance():
    mu = 1.1
    sigma = 0.25

    mean, std = tm.func.get_lognorm_mean_stdev(mu, sigma)

    mu2, sigma2 = tm.func.get_lognorm_mu_sigma_from_lognorm_mean_variance(mean, std ** 2)

    assert mu == pytest.approx(mu2)
    assert sigma == pytest.approx(sigma2)


def test_nonzero_velocity():
    velocity = np.ones(1)
    np.testing.assert_array_equal(
        tm.func.get_nonzero_velocity(velocity),
        np.ones(1))

    velocity = np.array([1, 2, 0, 4, 8 ,0])
    np.testing.assert_array_equal(
        tm.func.get_nonzero_velocity(velocity),
        np.array([1, 2, 4, 8]))
