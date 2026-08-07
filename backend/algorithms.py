# Phase 3 — Ranking Engine
# Implemented in Phase 3. Placeholder keeps imports from failing.


def insertion_sort_by_key(items: list[dict], key: str) -> list[dict]:
    """Sorts a list of dicts in descending order by a numeric key using insertion sort."""
    arr = list(items)
    for i in range(1, len(arr)):
        current = arr[i]
        j = i - 1
        while j >= 0 and arr[j][key] < current[key]:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = current
    return arr


def binary_search_iterative(sorted_titles: list[str], target: str) -> int:
    """Iterative binary search. Returns index or -1."""
    start, end = 0, len(sorted_titles) - 1
    while start <= end:
        mid = start + (end - start) // 2
        if sorted_titles[mid] == target:
            return mid
        elif sorted_titles[mid] < target:
            start = mid + 1
        else:
            end = mid - 1
    return -1


def binary_search_recursive(sorted_titles: list[str], target: str,
                             start: int, end: int) -> int:
    """Recursive binary search. Returns index or -1."""
    if start > end:
        return -1
    mid = start + (end - start) // 2
    if sorted_titles[mid] == target:
        return mid
    elif sorted_titles[mid] < target:
        return binary_search_recursive(sorted_titles, target, mid + 1, end)
    else:
        return binary_search_recursive(sorted_titles, target, start, mid - 1)


def linear_search(items: list[dict], key: str, value) -> dict | None:
    """Linear search with explicit found-flag. Returns first match or None."""
    found = False
    result = None
    for item in items:
        if item.get(key) == value:
            found = True
            result = item
            break
    return result if found else None
