import estimage.statops.compare as tm


def test_compare_trivial():
    assert tm.is_lower([0], [1], [1]) == 0.5


def test_compare_equal():
    assert tm.is_lower([0, 1], [1, 1], [1, 1]) == 0.5
    assert tm.is_lower([0, 1, 2], [1, 1, 1], [1, 1, 1]) == 0.5
    assert tm.is_lower([0, 1, 2, 3], [1, 1, 1, 1], [1, 1, 1, 1]) == 0.5
    assert tm.is_lower([0, 1, 2], [0, 1, 0], [1, 1, 1]) == 0.5


def test_compare_clear():
    assert tm.is_lower([0, 1], [0, 1], [1, 0]) == 0
    assert tm.is_lower([0, 1], [1, 0], [0, 1]) == 1
    assert tm.is_lower([0, 1, 2, 3], [1, 1, 0, 0], [0, 0, 1, 1]) == 1
    assert tm.is_lower([0, 1, 2, 3], [0, 0, 1, 1], [1, 1, 0, 0]) == 0


def test_compare_weighted():
    assert 0.99 < tm.is_lower([0, 1, 2, 3], [1, 1, 0, 0], [0, 0.01, 1, 1]) < 1

# TODO: Comparison of estimates
# TODO: %-complete
