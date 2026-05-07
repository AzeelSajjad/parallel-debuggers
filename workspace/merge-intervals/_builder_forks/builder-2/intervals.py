def merge_intervals(items):
    if not items:
        return []
    sorted_items = sorted(items, key=lambda x: (x[0], x[1]))
    merged = [sorted_items[0]]
    for start, end in sorted_items[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged
