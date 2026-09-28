from datetime import UTC, datetime

from apps.scheduling.services.intervals import merge_intervals, subtract_intervals


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 1, hour, minute, tzinfo=UTC)


class TestMergeIntervals:
    def test_empty_input(self):
        assert merge_intervals([]) == []

    def test_single_interval_unchanged(self):
        assert merge_intervals([(_dt(9), _dt(10))]) == [(_dt(9), _dt(10))]

    def test_disjoint_intervals_unchanged(self):
        intervals = [(_dt(9), _dt(10)), (_dt(11), _dt(12))]
        assert merge_intervals(intervals) == intervals

    def test_overlapping_intervals_merged(self):
        intervals = [(_dt(9), _dt(12)), (_dt(11), _dt(13))]
        assert merge_intervals(intervals) == [(_dt(9), _dt(13))]

    def test_touching_intervals_merged(self):
        intervals = [(_dt(9), _dt(11)), (_dt(11), _dt(13))]
        assert merge_intervals(intervals) == [(_dt(9), _dt(13))]

    def test_unsorted_input_sorted_correctly(self):
        intervals = [(_dt(11), _dt(13)), (_dt(9), _dt(10))]
        assert merge_intervals(intervals) == [(_dt(9), _dt(10)), (_dt(11), _dt(13))]

    def test_three_overlapping_intervals_collapse_to_one(self):
        intervals = [(_dt(9), _dt(12)), (_dt(11), _dt(13)), (_dt(13), _dt(15))]
        assert merge_intervals(intervals) == [(_dt(9), _dt(15))]


class TestSubtractIntervals:
    def test_empty_base_returns_empty(self):
        assert subtract_intervals([], [(_dt(9), _dt(10))]) == []

    def test_subtracting_nothing_returns_base_unchanged(self):
        base = [(_dt(9), _dt(18))]
        assert subtract_intervals(base, []) == base

    def test_subtracting_everything_returns_empty(self):
        base = [(_dt(9), _dt(18))]
        assert subtract_intervals(base, [(_dt(9), _dt(18))]) == []

    def test_subtracting_wider_range_returns_empty(self):
        base = [(_dt(9), _dt(18))]
        assert subtract_intervals(base, [(_dt(0), _dt(23))]) == []

    def test_lunch_break_shaped_subtraction(self):
        base = [(_dt(9), _dt(18))]
        subtract = [(_dt(13), _dt(14))]
        assert subtract_intervals(base, subtract) == [(_dt(9), _dt(13)), (_dt(14), _dt(18))]

    def test_subtract_at_start_clips_left_edge(self):
        base = [(_dt(9), _dt(18))]
        subtract = [(_dt(8), _dt(10))]
        assert subtract_intervals(base, subtract) == [(_dt(10), _dt(18))]

    def test_subtract_at_end_clips_right_edge(self):
        base = [(_dt(9), _dt(18))]
        subtract = [(_dt(17), _dt(19))]
        assert subtract_intervals(base, subtract) == [(_dt(9), _dt(17))]

    def test_multiple_base_intervals_subtracted_independently(self):
        base = [(_dt(9), _dt(12)), (_dt(14), _dt(18))]
        subtract = [(_dt(10), _dt(11)), (_dt(15), _dt(16))]
        assert subtract_intervals(base, subtract) == [
            (_dt(9), _dt(10)),
            (_dt(11), _dt(12)),
            (_dt(14), _dt(15)),
            (_dt(16), _dt(18)),
        ]

    def test_unsorted_and_unmerged_subtract_input_handled(self):
        base = [(_dt(9), _dt(18))]
        subtract = [(_dt(14), _dt(15)), (_dt(13), _dt(14, 30))]
        assert subtract_intervals(base, subtract) == [(_dt(9), _dt(13)), (_dt(15), _dt(18))]
