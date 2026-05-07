from intervals import merge_intervals


def test_empty():
    assert merge_intervals([]) == []


def test_overlapping_merge():
    assert merge_intervals([(1, 4), (3, 6)]) == [(1, 6)]


def test_touching_merge():
    assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]


def test_unsorted():
    assert merge_intervals([(5, 7), (1, 3)]) == [(1, 3), (5, 7)]


def test_complex_chain():
    assert merge_intervals(
        [(1, 4), (2, 5), (7, 9), (8, 10), (11, 11)]
    ) == [(1, 5), (7, 10), (11, 11)]
