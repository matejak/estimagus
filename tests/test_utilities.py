import pytest

import app.utilities as tm


@pytest.mark.dependency(name="test_set_reduction")
def test_set_reduction():
    assert tm.reduce_subsets_from_sets([]) == []
    assert tm.reduce_subsets_from_sets(["a"]) == ["a"]
    assert tm.reduce_subsets_from_sets(["a", "a"]) == ["a"]
    assert tm.reduce_subsets_from_sets(["a", "b"]) == ["a", "b"]
    assert tm.reduce_subsets_from_sets(["a", "b", "axe"]) == ["b", "axe"]
    assert tm.reduce_subsets_from_sets(["a", "axe", "b"]) == ["axe", "b"]

