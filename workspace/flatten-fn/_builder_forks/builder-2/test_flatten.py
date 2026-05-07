from flatten import flatten


def test_flat_list_unchanged():
    assert flatten([1, 2, 3]) == [1, 2, 3]


def test_one_level_nesting():
    assert flatten([1, [2, 3], 4]) == [1, 2, 3, 4]


def test_deeply_nested():
    assert flatten([1, [2, [3, [4, [5]]]]]) == [1, 2, 3, 4, 5]


def test_strings_are_atomic():
    """Strings are iterable but must NOT be flattened into characters."""
    assert flatten([1, "ab", [3, "cd"]]) == [1, "ab", 3, "cd"]


def test_empty_list():
    assert flatten([]) == []


def test_nested_empties():
    assert flatten([[], [1], [], [[2]]]) == [1, 2]


def test_tuples_are_flattened():
    """Tuples are treated as nested containers (like lists)."""
    assert flatten([1, (2, 3), [4]]) == [1, 2, 3, 4]


def test_mixed_lists_and_tuples():
    assert flatten([(1, [2]), [3, (4, 5)]]) == [1, 2, 3, 4, 5]
