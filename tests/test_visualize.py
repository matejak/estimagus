import numpy as np

import estimage.visualize as tm
import estimage.visualize.utils


def test_element_insertion():
    a = np.array([1])
    new_a = tm.utils.insert_element_into_array_after(a, 0, 2)
    np.testing.assert_array_equal(new_a, np.array([1, 2]))


def test_simplify_history():
    trivial_input = np.array([])
    assert len(tm.utils.simplify_timeline_array(trivial_input)) == 0

    simple_input = np.array([[1, 2]])
    np.testing.assert_array_equal(tm.utils.simplify_timeline_array(simple_input), simple_input)

    minimal_input = np.array([[1, 2], [1, 2]])
    np.testing.assert_array_equal(tm.utils.simplify_timeline_array(minimal_input), minimal_input)

    redundant_input = np.array([[1, 2], [1, 2], [1, 2]])
    np.testing.assert_array_equal(tm.utils.simplify_timeline_array(redundant_input), minimal_input)

    np.testing.assert_array_equal(tm.utils.simplify_timeline_array(
        np.array([[1, 2], [1.5, 2], [2, 2]])), np.array([[1, 2], [2, 2]]))

    np.testing.assert_array_equal(tm.utils.simplify_timeline_array(
        np.array([[1, 2], [1.5, 2], [1.8, 2], [2, 2], [2, 2]])), np.array([[1, 2], [2, 2]]))

    np.testing.assert_array_equal(tm.utils.simplify_timeline_array(
        np.array([[1, 2], [1.5, 2], [1.8, 2], [2, 3], [4, 3]])), np.array([[1, 2], [1.8, 2], [2, 3], [4, 3]]))

    np.testing.assert_array_equal(
        tm.utils.simplify_timeline_array(
            np.array([[1, 2, 0], [1.5, 2, 0], [1.8, 2, 1], [2, 3, 1], [3, 3, 1], [4, 3, 1]])),
            np.array([[1, 2, 0], [1.5, 2, 0], [1.8, 2, 1], [2, 3, 1], [4, 3, 1]]))


