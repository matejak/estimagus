import pytest

import numpy as np

import estimage.utilities as tm


@pytest.mark.dependency(name="test_set_reduction_trivial")
def test_set_reduction_trivial():
    assert tm.reduce_subsets_from_sets([]) == []
    assert tm.reduce_subsets_from_sets(["a"]) == ["a"]


@pytest.mark.dependency(depends=["test_set_reduction_trivial"])
def test_set_reduction_normal():
    assert tm.reduce_subsets_from_sets(["a", "a"]) == ["a"]
    assert tm.reduce_subsets_from_sets(["a", "b"]) == ["a", "b"]
    assert tm.reduce_subsets_from_sets(["a", "b", "axe"]) == ["b", "axe"]
    assert tm.reduce_subsets_from_sets(["a", "axe", "b"]) == ["axe", "b"]
    assert tm.reduce_subsets_from_sets(["a", "axe", "a"]) == ["axe"]


def test_first_nonzero_index():
    arr = np.array([1])
    assert tm.first_nonzero_index_of(arr) == 0
    arr = np.array([0, 1])
    assert tm.first_nonzero_index_of(arr) == 1
    arr = np.array([0])
    with pytest.raises(ValueError):
        tm.first_nonzero_index_of(arr)
    with pytest.raises(ValueError):
        tm.first_nonzero_index_of(np.array([]))


def test_last_nonzero_index():
    arr = np.array([1])
    assert tm.last_nonzero_index_of(arr) == 0
    arr = np.array([0, 1])
    assert tm.last_nonzero_index_of(arr) == 1
    arr = np.array([0, 1, 0, 0])
    assert tm.last_nonzero_index_of(arr) == 1
    arr = np.array([0])
    with pytest.raises(ValueError):
        tm.last_nonzero_index_of(arr)
    with pytest.raises(ValueError):
        tm.last_nonzero_index_of(np.array([]))
