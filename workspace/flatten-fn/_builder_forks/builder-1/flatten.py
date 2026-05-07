def flatten(items):
    """Recursively flatten nested lists and tuples into a single flat list.

    Strings are treated as atomic values and are not flattened into characters.
    """
    result = []
    for item in items:
        if isinstance(item, (list, tuple)):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result
