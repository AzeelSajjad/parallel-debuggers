def merge_intervals(items):
    """Merge overlapping or touching intervals.

    Args:
        items: An iterable of (start, end) tuples. Not required to be sorted.

    Returns:
        A list of (start, end) tuples representing the merged, non-overlapping
        intervals sorted by start. Touching intervals (where one ends where
        the next begins) are merged. Point intervals (start == end) are
        preserved.
    """
    if not items:
        return []

    sorted_items = sorted(items, key=lambda iv: (iv[0], iv[1]))

    merged = [sorted_items[0]]
    for start, end in sorted_items[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            if end > last_end:
                merged[-1] = (last_start, end)
        else:
            merged.append((start, end))

    return merged
