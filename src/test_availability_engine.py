"""Tests for the Room Availability Engine.

We verify that the engine correctly excludes rooms that have overlapping
entries, respects the effective date range of date-dependent entries, and
honours a minimum capacity requirement.

Test dates are chosen based on ACTUAL timetable data verified from the DB.
- 2026-08-10 (Monday): EB1-101 has classes at 12:00, 13:00, 14:00 (NOT 09:00).
- 2026-08-12 (Wednesday): EB1-101 has a class at 09:00-09:50.
- EB2-006 is fully occupied on Monday but FREE on Wednesday at 13:00.
- IET Amphitheatre is occupied on Sunday 2026-08-09 (Monday 15:00-15:50 within Aug).
- LRC002 has no Monday entries at all.
"""
import unittest
import datetime
from pathlib import Path

import sys
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.availability_engine import find_available_rooms


class TestAvailabilityEngine(unittest.TestCase):

    def test_occupied_room(self):
        """EB1-101 has a class on Wednesday 09:00-09:50; it must be excluded."""
        # 2026-08-12 is a Wednesday
        rooms = find_available_rooms("2026-08-12", "09:00", "09:50")
        room_numbers = {r["room_number"] for r in rooms}
        self.assertNotIn(
            "EB1-101", room_numbers,
            "EB1-101 should be excluded because it has a class on Wednesday 09:00-09:50."
        )

    def test_completely_free_room(self):
        """LRC002 has no entries on Monday at all; it must appear as free."""
        # 2026-08-10 is a Monday; LRC002 has zero Monday timetable entries.
        rooms = find_available_rooms("2026-08-10", "09:00", "09:50")
        room_numbers = {r["room_number"] for r in rooms}
        self.assertIn(
            "LRC002", room_numbers,
            "LRC002 should be available because it has no class on Monday 09:00-09:50."
        )

    def test_partial_time_overlap(self):
        """EB1-101 has a class on Wednesday 09:00-09:50; a 09:30-10:00 request overlaps."""
        rooms = find_available_rooms("2026-08-12", "09:30", "10:00")
        room_numbers = {r["room_number"] for r in rooms}
        self.assertNotIn(
            "EB1-101", room_numbers,
            "EB1-101 should be excluded due to partial overlap with 09:00-09:50 class."
        )

    def test_capacity_requirement(self):
        """Requesting min_capacity=200 returns no rooms (max known capacity is 100)."""
        rooms = find_available_rooms("2026-08-10", "09:00", "09:50", min_capacity=200)
        self.assertEqual(
            len(rooms), 0,
            "No rooms should be returned when min_capacity=200 (exceeds all known capacities)."
        )

    def test_date_dependent_room_availability(self):
        """IET Amphitheatre is occupied on Monday 15:00-15:50 only within Aug 2026.
        IM Amphitheatre takes over for the same slot from Sep 2026."""
        # 2026-08-09 is a Sunday --- pick 2026-08-10 (Monday) which is within Aug
        rooms_aug = find_available_rooms("2026-08-10", "15:00", "15:50")
        room_numbers_aug = {r["room_number"] for r in rooms_aug}
        self.assertNotIn(
            "IET Amphitheatre", room_numbers_aug,
            "IET Amphitheatre should be occupied on Monday 15:00-15:50 in August."
        )
        # 2026-09-07 is a Monday, in September -> IM Amphitheatre takes the slot
        rooms_sep = find_available_rooms("2026-09-07", "15:00", "15:50")
        room_numbers_sep = {r["room_number"] for r in rooms_sep}
        self.assertNotIn(
            "IM Amphitheatre", room_numbers_sep,
            "IM Amphitheatre should be occupied on Monday 15:00-15:50 in September."
        )

    def test_byod_lab_availability(self):
        """BYOD is free on Monday 11:00-11:30 (its Monday slots are 09:00, 10:00, 12:00, 14:00, 15:00)."""
        rooms = find_available_rooms("2026-08-10", "11:00", "11:30")
        room_numbers = {r["room_number"] for r in rooms}
        self.assertIn(
            "BYOD", room_numbers,
            "BYOD should be free on Monday 11:00-11:30 (no timetable entry for that slot)."
        )


if __name__ == "__main__":
    unittest.main()
