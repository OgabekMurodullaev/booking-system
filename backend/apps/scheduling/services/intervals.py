from datetime import datetime

Interval = tuple[datetime, datetime]


def merge_intervals(intervals: list[Interval]) -> list[Interval]:
    """Merge overlapping/touching half-open [start, end) intervals into a minimal sorted set."""
    if not intervals:
        return []

    ordered = sorted(intervals, key=lambda interval: interval[0])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def subtract_intervals(base: list[Interval], subtract: list[Interval]) -> list[Interval]:
    """Return base minus every interval in subtract (half-open interval set difference).

    Neither list needs to be pre-sorted or pre-merged.
    """
    if not base:
        return []

    blocked = merge_intervals(subtract)
    result: list[Interval] = []
    for b_start, b_end in sorted(base, key=lambda interval: interval[0]):
        cursor = b_start
        for s_start, s_end in blocked:
            if s_end <= cursor or s_start >= b_end:
                continue
            if s_start > cursor:
                result.append((cursor, min(s_start, b_end)))
            cursor = max(cursor, s_end)
            if cursor >= b_end:
                break
        if cursor < b_end:
            result.append((cursor, b_end))
    return result
