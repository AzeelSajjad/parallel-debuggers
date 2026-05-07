from intervals import merge_intervals


def test_empty_input():
    assert merge_intervals([]) == []


def test_single_interval():
    assert merge_intervals([(1, 3)]) == [(1, 3)]


def test_disjoint_intervals():
    assert merge_intervals([(1, 3), (5, 7)]) == [(1, 3), (5, 7)]


def test_overlapping_intervals_merge():
    assert merge_intervals([(1, 4), (3, 6)]) == [(1, 6)]


def test_touching_intervals_merge():
    assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]


def test_unsorted_input_is_handled():
    assert merge_intervals([(5, 7), (1, 3)]) == [(1, 3), (5, 7)]


def test_one_interval_contains_another():
    assert merge_intervals([(1, 10), (3, 5)]) == [(1, 10)]


def test_point_interval_preserved():
    assert merge_intervals([(3, 3)]) == [(3, 3)]


def test_complex_chain():
    assert merge_intervals(
        [(1, 4), (2, 5), (7, 9), (8, 10), (11, 11)]
    ) == [(1, 5), (7, 10), (11, 11)]
