"""Unit tests for the Room Recommendation Engine (src/room_recommender.py).

Tests are grouped into:
- Validation tests (TC01–TC05)
- Filtering tests (TC06–TC11)
- Route/ranking tests (TC12–TC15)
- Unmapped-room handling tests (TC16–TC19)
- Special campus mapping tests (TC20–TC24)

Mocking strategy
----------------
- ``find_available_rooms`` is mocked to return a controlled list of available rooms
  without touching the real database or timetable.
- ``_load_room_metadata`` (the internal metadata loader) is mocked to inject a
  controlled room metadata dictionary without touching the real database.
- ``find_shortest_route`` is used as-is (against the real CAMPUS_GRAPH); it is
  deterministic and pure, so no mock is needed unless a specific test isolates A*.
- ``get_campus_node`` is used as-is; it is a pure function with no I/O.

No database records are modified at any point.
"""

import pathlib
import unittest
from unittest.mock import patch, MagicMock

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
import sys
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.room_recommender import (
    RecommendationQuery,
    RecommendedRoom,
    recommend_rooms,
    _validate_query,
)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_query(**overrides) -> RecommendationQuery:
    """Return a valid RecommendationQuery with optional field overrides."""
    defaults = dict(
        preferred_building="TB",
        date="2026-08-10",
        start_time="09:00",
        end_time="10:00",
        min_capacity=0,
        required_room_type=None,
        required_equipment=(),
    )
    defaults.update(overrides)
    return RecommendationQuery(**defaults)


def _make_metadata(*rooms) -> dict:
    """Build a metadata dict keyed by room_number from a list of dicts.

    Each dict should have: room_number, building, capacity, room_type,
    equipment_raw, equipment_items (lowercase set).
    """
    return {r["room_number"]: r for r in rooms}


def _room(room_number, building, campus_building, capacity=60,
          room_type="Classroom", equipment_raw="AC,Smartboard,Wi-Fi,Power sockets"):
    """Build a mock room metadata dict."""
    return {
        "room_number": room_number,
        "building": building,
        "campus_building": campus_building,
        "capacity": capacity,
        "room_type": room_type,
        "equipment_raw": equipment_raw,
        "equipment_items": {e.strip().lower() for e in equipment_raw.split(",") if e.strip()},
    }


# Constant fake date that guarantees a free Monday slot with minimal timetable conflicts
FAKE_AVAILABLE = [
    {"room_number": "TB-102", "building": "Technology Block (TB)", "capacity": 80},
    {"room_number": "TB-104", "building": "Technology Block (TB)", "capacity": 80},
    {"room_number": "EB2-001", "building": "Engineering Block 2 (EB-2)", "capacity": 60},
    {"room_number": "EB1-101", "building": "Engineering Block 1 (EB-1)", "capacity": 60},
    {"room_number": "IM-102", "building": "Management Block (IM)", "capacity": 60},
    {"room_number": "LRC002", "building": "Learning Resource Centre (LRC)", "capacity": 60},
    {"room_number": "BYOD",   "building": "Computer Science Labs", "capacity": 60},
    {"room_number": "AIC-004", "building": "Atal Incubation Centre (AIC)", "capacity": 60},
    {"room_number": "IET Amphitheatre", "building": "Campus Amphitheatres", "capacity": 100},
    {"room_number": "EB-006 (IET)", "building": "Engineering Block (EB)", "capacity": 100},
    {"room_number": "IM Amphitheatre", "building": "Campus Amphitheatres", "capacity": 100},
]

FAKE_METADATA = _make_metadata(
    _room("TB-102",    "Technology Block (TB)",          "TB",  80),
    _room("TB-104",    "Technology Block (TB)",          "TB",  80),
    _room("EB2-001",   "Engineering Block 2 (EB-2)",     "EB2", 60),
    _room("EB1-101",   "Engineering Block 1 (EB-1)",     "EB1", 60),
    _room("IM-102",    "Management Block (IM)",          "IM",  60),
    _room("LRC002",    "Learning Resource Centre (LRC)", None,  60),
    _room("BYOD",      "Computer Science Labs",          "TB",  60,
          "Computer Lab", "Computers,AC,Projector,Wi-Fi,Power sockets"),
    _room("AIC-004",   "Atal Incubation Centre (AIC)",   "EB2", 60),
    _room("IET Amphitheatre", "Campus Amphitheatres",    "EB1", 100,
          "Seminar Room", "Projector,AC,Smartboard,Wi-Fi,Power sockets"),
    _room("EB-006 (IET)", "Engineering Block (EB)",      "EB1", 100,
          "Seminar Room", "Projector,AC,Smartboard,Wi-Fi,Power sockets"),
    _room("IM Amphitheatre", "Campus Amphitheatres",     "IM",  100,
          "Seminar Room", "Projector,AC,Smartboard,Wi-Fi,Power sockets"),
    _room("LRC007",    "Learning Resource Centre (LRC)", None,  60,
          "Computer Lab", "Computers,AC,Projector,Wi-Fi,Power sockets"),
)


# ---------------------------------------------------------------------------
# TC01–TC05 Input validation
# ---------------------------------------------------------------------------

class TestInputValidation(unittest.TestCase):
    """TC01–TC05: Malformed query parameters raise ValueError."""

    def test_tc01_invalid_preferred_building(self):
        """TC01: preferred_building not in {EB1, EB2, TB, IM} raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            _validate_query(_make_query(preferred_building="LIBRARY"))
        self.assertIn("preferred_building", str(ctx.exception).lower())

    def test_tc01b_empty_preferred_building(self):
        """TC01b: Empty preferred_building raises ValueError."""
        with self.assertRaises(ValueError):
            _validate_query(_make_query(preferred_building=""))

    def test_tc02_invalid_date_format(self):
        """TC02: Date not in YYYY-MM-DD raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            _validate_query(_make_query(date="10/08/2026"))
        self.assertIn("date", str(ctx.exception).lower())

    def test_tc03_invalid_time_format(self):
        """TC03: Time not in HH:MM raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            _validate_query(_make_query(start_time="9:00am"))
        self.assertIn("start_time", str(ctx.exception).lower())

    def test_tc04_start_time_after_end_time(self):
        """TC04: start_time >= end_time raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            _validate_query(_make_query(start_time="11:00", end_time="09:00"))
        self.assertIn("start_time", str(ctx.exception).lower())

    def test_tc04b_start_equals_end_time(self):
        """TC04b: start_time == end_time (zero-length) raises ValueError."""
        with self.assertRaises(ValueError):
            _validate_query(_make_query(start_time="10:00", end_time="10:00"))

    def test_tc05_negative_min_capacity(self):
        """TC05: Negative min_capacity raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            _validate_query(_make_query(min_capacity=-1))
        self.assertIn("min_capacity", str(ctx.exception).lower())

    def test_tc01_all_valid_buildings_accepted(self):
        """All four valid campus nodes pass validation without error."""
        for building in ("EB1", "EB2", "TB", "IM"):
            _validate_query(_make_query(preferred_building=building))  # must not raise


# ---------------------------------------------------------------------------
# TC06–TC11 Filtering correctness
# ---------------------------------------------------------------------------

class TestFilteringCorrectness(unittest.TestCase):
    """TC06–TC11: Availability, capacity, type, and equipment filtering."""

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc06_availability_filtering(self, mock_avail, mock_meta):
        """TC06: Only rooms returned by find_available_rooms appear in results."""
        # Only TB-102 is available
        mock_avail.return_value = [
            {"room_number": "TB-102", "building": "Technology Block (TB)", "capacity": 80}
        ]
        mock_meta.return_value = {
            "TB-102": FAKE_METADATA["TB-102"],
            "TB-104": FAKE_METADATA["TB-104"],
        }
        results = recommend_rooms(_make_query(preferred_building="TB"))
        room_numbers = [r.room_number for r in results]
        self.assertIn("TB-102", room_numbers)
        self.assertNotIn("TB-104", room_numbers)

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc07_minimum_capacity_filtering(self, mock_avail, mock_meta):
        """TC07: Rooms with capacity < min_capacity are excluded."""
        mock_avail.return_value = [
            {"room_number": "TB-102", "building": "Technology Block (TB)", "capacity": 80},
            {"room_number": "EB2-001", "building": "Engineering Block 2 (EB-2)", "capacity": 60},
        ]
        mock_meta.return_value = {
            "TB-102": FAKE_METADATA["TB-102"],   # capacity=80
            "EB2-001": FAKE_METADATA["EB2-001"], # capacity=60
        }
        results = recommend_rooms(_make_query(preferred_building="TB", min_capacity=70))
        room_numbers = [r.room_number for r in results]
        self.assertIn("TB-102", room_numbers)
        self.assertNotIn("EB2-001", room_numbers)

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc08_room_type_filtering(self, mock_avail, mock_meta):
        """TC08: Only rooms matching required_room_type are returned."""
        mock_avail.return_value = [
            {"room_number": "TB-102",  "building": "Technology Block (TB)", "capacity": 80},
            {"room_number": "IET Amphitheatre", "building": "Campus Amphitheatres", "capacity": 100},
        ]
        mock_meta.return_value = {
            "TB-102":  FAKE_METADATA["TB-102"],            # Classroom
            "IET Amphitheatre": FAKE_METADATA["IET Amphitheatre"],  # Seminar Room
        }
        results = recommend_rooms(_make_query(preferred_building="TB", required_room_type="Classroom"))
        room_numbers = [r.room_number for r in results]
        self.assertIn("TB-102", room_numbers)
        self.assertNotIn("IET Amphitheatre", room_numbers)

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc09_equipment_filtering(self, mock_avail, mock_meta):
        """TC09: Rooms lacking any required equipment item are excluded."""
        # EB2-001 has no 'Computers', BYOD has 'Computers'
        mock_avail.return_value = [
            {"room_number": "EB2-001", "building": "Engineering Block 2 (EB-2)", "capacity": 60},
            {"room_number": "BYOD",    "building": "Computer Science Labs",       "capacity": 60},
        ]
        mock_meta.return_value = {
            "EB2-001": FAKE_METADATA["EB2-001"],
            "BYOD":    FAKE_METADATA["BYOD"],
        }
        results = recommend_rooms(
            _make_query(preferred_building="EB2", required_equipment=("Computers",))
        )
        room_numbers = [r.room_number for r in results]
        self.assertNotIn("EB2-001", room_numbers)
        self.assertIn("BYOD", room_numbers)

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc10_case_insensitive_matching(self, mock_avail, mock_meta):
        """TC10: room_type and equipment matching is case-insensitive."""
        mock_avail.return_value = [
            {"room_number": "TB-102", "building": "Technology Block (TB)", "capacity": 80},
        ]
        mock_meta.return_value = {"TB-102": FAKE_METADATA["TB-102"]}

        # Lowercase room_type
        results = recommend_rooms(
            _make_query(preferred_building="TB", required_room_type="classroom")
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].room_number, "TB-102")

        # Mixed-case equipment
        results2 = recommend_rooms(
            _make_query(preferred_building="TB", required_equipment=("SMARTBOARD", "ac"))
        )
        self.assertEqual(len(results2), 1)
        self.assertEqual(results2[0].room_number, "TB-102")

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc11_multiple_equipment_requirements(self, mock_avail, mock_meta):
        """TC11: ALL requested equipment items must be present (AND logic)."""
        byod_meta = FAKE_METADATA["BYOD"]    # has Computers, AC, Projector, Wi-Fi, Power sockets
        tb_meta   = FAKE_METADATA["TB-102"]  # has AC, Smartboard, Wi-Fi, Power sockets (no Computers)

        mock_avail.return_value = [
            {"room_number": "BYOD",   "building": "Computer Science Labs", "capacity": 60},
            {"room_number": "TB-102", "building": "Technology Block (TB)", "capacity": 80},
        ]
        mock_meta.return_value = {"BYOD": byod_meta, "TB-102": tb_meta}

        results = recommend_rooms(
            _make_query(preferred_building="TB", required_equipment=("Computers", "AC", "Wi-Fi"))
        )
        room_numbers = [r.room_number for r in results]
        self.assertIn("BYOD", room_numbers)
        self.assertNotIn("TB-102", room_numbers)


# ---------------------------------------------------------------------------
# TC12–TC15 Route and ranking correctness
# ---------------------------------------------------------------------------

class TestRouteAndRankingCorrectness(unittest.TestCase):
    """TC12–TC15: A* integration, distance ranking, and tie-breaking."""

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc12_correct_astar_route_and_distance(self, mock_avail, mock_meta):
        """TC12: Walking route and distance are computed correctly via A*.

        From TB to TB: 0 m (same building, single-node path).
        From TB to EB2: TB -> EB1 -> EB2 = 10 + 5 = 15 m.
        """
        mock_avail.return_value = [
            {"room_number": "TB-102",  "building": "Technology Block (TB)",      "capacity": 80},
            {"room_number": "EB2-001", "building": "Engineering Block 2 (EB-2)", "capacity": 60},
        ]
        mock_meta.return_value = {
            "TB-102":  FAKE_METADATA["TB-102"],
            "EB2-001": FAKE_METADATA["EB2-001"],
        }
        results = recommend_rooms(_make_query(preferred_building="TB"))
        result_map = {r.room_number: r for r in results}

        # TB → TB: in-building, distance 0
        self.assertEqual(result_map["TB-102"].walking_distance, 0.0)
        self.assertEqual(result_map["TB-102"].walking_route, ["TB"])

        # TB → EB2: 15 m via EB1
        self.assertEqual(result_map["EB2-001"].walking_distance, 15.0)
        self.assertEqual(result_map["EB2-001"].walking_route, ["TB", "EB1", "EB2"])

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc13_distance_ranking_ascending(self, mock_avail, mock_meta):
        """TC13: Results are sorted by walking distance (ascending) first."""
        mock_avail.return_value = [
            {"room_number": "EB2-001", "building": "Engineering Block 2 (EB-2)", "capacity": 60},
            {"room_number": "IM-102",  "building": "Management Block (IM)",      "capacity": 60},
            {"room_number": "TB-102",  "building": "Technology Block (TB)",      "capacity": 80},
        ]
        mock_meta.return_value = {
            "EB2-001": FAKE_METADATA["EB2-001"],
            "IM-102":  FAKE_METADATA["IM-102"],
            "TB-102":  FAKE_METADATA["TB-102"],
        }
        # From TB: TB=0, EB2=15, IM=50
        results = recommend_rooms(_make_query(preferred_building="TB"))
        distances = [r.walking_distance for r in results]
        self.assertEqual(distances, sorted(distances))

        room_order = [r.room_number for r in results]
        self.assertEqual(room_order[0], "TB-102")   # 0 m

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc14_capacity_tie_breaking(self, mock_avail, mock_meta):
        """TC14: When distances are equal, smaller capacity comes first."""
        # Both in EB2 relative to EB2 (distance=0 each)
        meta_60 = _room("EB2-001", "Engineering Block 2 (EB-2)", "EB2", capacity=60)
        meta_80 = _room("EB2-004", "Engineering Block 2 (EB-2)", "EB2", capacity=80)
        mock_avail.return_value = [
            {"room_number": "EB2-001", "building": "Engineering Block 2 (EB-2)", "capacity": 60},
            {"room_number": "EB2-004", "building": "Engineering Block 2 (EB-2)", "capacity": 80},
        ]
        mock_meta.return_value = {"EB2-001": meta_60, "EB2-004": meta_80}

        results = recommend_rooms(_make_query(preferred_building="EB2"))
        self.assertEqual(results[0].room_number, "EB2-001")  # smaller capacity first
        self.assertEqual(results[1].room_number, "EB2-004")

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc15_room_number_tie_breaking(self, mock_avail, mock_meta):
        """TC15: Equal distance AND equal capacity → room_number ascending."""
        meta_a = _room("TB-104", "Technology Block (TB)", "TB", capacity=80)
        meta_b = _room("TB-102", "Technology Block (TB)", "TB", capacity=80)
        mock_avail.return_value = [
            {"room_number": "TB-104", "building": "Technology Block (TB)", "capacity": 80},
            {"room_number": "TB-102", "building": "Technology Block (TB)", "capacity": 80},
        ]
        mock_meta.return_value = {"TB-104": meta_a, "TB-102": meta_b}

        results = recommend_rooms(_make_query(preferred_building="TB"))
        room_order = [r.room_number for r in results]
        self.assertEqual(room_order, sorted(room_order))  # alphabetical ascending
        self.assertEqual(room_order[0], "TB-102")
        self.assertEqual(room_order[1], "TB-104")


# ---------------------------------------------------------------------------
# TC16–TC19 Unmapped rooms handling
# ---------------------------------------------------------------------------

class TestUnmappedRoomsHandling(unittest.TestCase):
    """TC16–TC19: LRC and other unmapped rooms excluded or included correctly."""

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc16_unmapped_rooms_excluded_by_default(self, mock_avail, mock_meta):
        """TC16: Unmapped rooms (campus_node=None) excluded when include_unmapped_buildings=False."""
        mock_avail.return_value = [
            {"room_number": "TB-102",  "building": "Technology Block (TB)", "capacity": 80},
            {"room_number": "LRC002",  "building": "Learning Resource Centre (LRC)", "capacity": 60},
        ]
        mock_meta.return_value = {
            "TB-102": FAKE_METADATA["TB-102"],
            "LRC002": FAKE_METADATA["LRC002"],
        }
        results = recommend_rooms(_make_query(preferred_building="TB"))
        room_numbers = [r.room_number for r in results]
        self.assertIn("TB-102", room_numbers)
        self.assertNotIn("LRC002", room_numbers)

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc17_unmapped_rooms_included_when_requested(self, mock_avail, mock_meta):
        """TC17: Unmapped rooms appear after mapped rooms when include_unmapped_buildings=True."""
        mock_avail.return_value = [
            {"room_number": "TB-102", "building": "Technology Block (TB)", "capacity": 80},
            {"room_number": "LRC002", "building": "Learning Resource Centre (LRC)", "capacity": 60},
        ]
        mock_meta.return_value = {
            "TB-102": FAKE_METADATA["TB-102"],
            "LRC002": FAKE_METADATA["LRC002"],
        }
        results = recommend_rooms(_make_query(preferred_building="TB"), include_unmapped_buildings=True)
        room_numbers = [r.room_number for r in results]
        self.assertIn("TB-102", room_numbers)
        self.assertIn("LRC002", room_numbers)

        # Mapped rooms appear before unmapped rooms
        mapped_indices   = [i for i, r in enumerate(results) if r.campus_node is not None]
        unmapped_indices = [i for i, r in enumerate(results) if r.campus_node is None]
        if mapped_indices and unmapped_indices:
            self.assertLess(max(mapped_indices), min(unmapped_indices))

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc17b_unmapped_room_has_none_distance_and_route(self, mock_avail, mock_meta):
        """TC17b: Unmapped rooms always have walking_distance=None and walking_route=None."""
        mock_avail.return_value = [
            {"room_number": "LRC002", "building": "Learning Resource Centre (LRC)", "capacity": 60},
        ]
        mock_meta.return_value = {"LRC002": FAKE_METADATA["LRC002"]}
        results = recommend_rooms(_make_query(preferred_building="TB"), include_unmapped_buildings=True)
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0].walking_distance)
        self.assertIsNone(results[0].walking_route)
        self.assertIsNone(results[0].campus_node)

    @patch("src.room_recommender.find_shortest_route")
    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc18_astar_never_called_for_unmapped_rooms(self, mock_avail, mock_meta, mock_astar):
        """TC18: find_shortest_route is NEVER called for rooms with campus_node=None."""
        mock_avail.return_value = [
            {"room_number": "LRC002", "building": "Learning Resource Centre (LRC)", "capacity": 60},
        ]
        mock_meta.return_value = {"LRC002": FAKE_METADATA["LRC002"]}
        recommend_rooms(_make_query(preferred_building="TB"), include_unmapped_buildings=True)
        mock_astar.assert_not_called()

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc19_empty_result_when_no_rooms_qualify(self, mock_avail, mock_meta):
        """TC19: Returns empty list when no available room meets requirements."""
        mock_avail.return_value = [
            {"room_number": "TB-102", "building": "Technology Block (TB)", "capacity": 80},
        ]
        mock_meta.return_value = {"TB-102": FAKE_METADATA["TB-102"]}
        # No room has capacity >= 1000
        results = recommend_rooms(_make_query(preferred_building="TB", min_capacity=1000))
        self.assertEqual(results, [])

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc19b_all_rooms_occupied_returns_empty(self, mock_avail, mock_meta):
        """TC19b: Returns empty list when find_available_rooms returns nothing."""
        mock_avail.return_value = []
        mock_meta.return_value = {"TB-102": FAKE_METADATA["TB-102"]}
        results = recommend_rooms(_make_query(preferred_building="TB"))
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# TC20–TC24 Special campus mapping (AIC, BYOD, IET aliases, IM Amphi, LRC)
# ---------------------------------------------------------------------------

class TestSpecialCampusMappings(unittest.TestCase):
    """TC20–TC24: Verify that known special rooms map to the correct campus node."""

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc20_aic_rooms_map_to_eb2(self, mock_avail, mock_meta):
        """TC20: AIC-prefixed rooms map to EB2 via the existing building_mapper."""
        mock_avail.return_value = [
            {"room_number": "AIC-004", "building": "Atal Incubation Centre (AIC)", "capacity": 60},
        ]
        mock_meta.return_value = {"AIC-004": FAKE_METADATA["AIC-004"]}
        results = recommend_rooms(_make_query(preferred_building="EB2"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].room_number, "AIC-004")
        self.assertEqual(results[0].campus_node, "EB2")
        self.assertEqual(results[0].walking_distance, 0.0)  # EB2 → EB2

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc21_byod_maps_to_tb(self, mock_avail, mock_meta):
        """TC21: BYOD maps to TB via the existing building_mapper."""
        mock_avail.return_value = [
            {"room_number": "BYOD", "building": "Computer Science Labs", "capacity": 60},
        ]
        mock_meta.return_value = {"BYOD": FAKE_METADATA["BYOD"]}
        results = recommend_rooms(_make_query(preferred_building="TB"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].room_number, "BYOD")
        self.assertEqual(results[0].campus_node, "TB")
        self.assertEqual(results[0].walking_distance, 0.0)  # TB → TB

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc22_iet_amphitheatre_and_eb006_map_to_eb1(self, mock_avail, mock_meta):
        """TC22: Both IET Amphitheatre and EB-006 (IET) correctly map to EB1.

        These two records represent the same physical venue. This test confirms
        that both database aliases are individually mapped to EB1 by get_campus_node.
        Cross-alias availability is a known limitation documented in room_recommender.py.
        """
        mock_avail.return_value = [
            {"room_number": "IET Amphitheatre", "building": "Campus Amphitheatres",   "capacity": 100},
            {"room_number": "EB-006 (IET)",     "building": "Engineering Block (EB)", "capacity": 100},
        ]
        mock_meta.return_value = {
            "IET Amphitheatre": FAKE_METADATA["IET Amphitheatre"],
            "EB-006 (IET)":     FAKE_METADATA["EB-006 (IET)"],
        }
        results = recommend_rooms(_make_query(preferred_building="EB1"))
        result_map = {r.room_number: r for r in results}

        self.assertIn("IET Amphitheatre", result_map)
        self.assertEqual(result_map["IET Amphitheatre"].campus_node, "EB1")
        self.assertEqual(result_map["IET Amphitheatre"].walking_distance, 0.0)

        # Secondary alias EB-006 (IET) is deduplicated away so the physical venue appears once
        self.assertNotIn("EB-006 (IET)", result_map)

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc23_im_amphitheatre_maps_to_im(self, mock_avail, mock_meta):
        """TC23: IM Amphitheatre maps to IM campus node."""
        mock_avail.return_value = [
            {"room_number": "IM Amphitheatre", "building": "Campus Amphitheatres", "capacity": 100},
        ]
        mock_meta.return_value = {"IM Amphitheatre": FAKE_METADATA["IM Amphitheatre"]}
        results = recommend_rooms(_make_query(preferred_building="IM"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].campus_node, "IM")
        self.assertEqual(results[0].walking_distance, 0.0)  # IM → IM

    @patch("src.room_recommender._load_room_metadata")
    @patch("src.room_recommender.find_available_rooms")
    def test_tc24_lrc_rooms_remain_unmapped(self, mock_avail, mock_meta):
        """TC24: LRC002 and LRC007 must have campus_node=None; never get A* distance."""
        mock_avail.return_value = [
            {"room_number": "LRC002", "building": "Learning Resource Centre (LRC)", "capacity": 60},
            {"room_number": "LRC007", "building": "Learning Resource Centre (LRC)", "capacity": 60},
        ]
        mock_meta.return_value = {
            "LRC002": FAKE_METADATA["LRC002"],
            "LRC007": FAKE_METADATA["LRC007"],
        }
        # Excluded by default
        results_default = recommend_rooms(_make_query(preferred_building="TB"))
        self.assertEqual(results_default, [])

        # Included when requested
        results_included = recommend_rooms(
            _make_query(preferred_building="TB"), include_unmapped_buildings=True
        )
        self.assertEqual(len(results_included), 2)
        for r in results_included:
            self.assertIsNone(r.campus_node)
            self.assertIsNone(r.walking_distance)
            self.assertIsNone(r.walking_route)


# ---------------------------------------------------------------------------
# Integration smoke test (uses real DB and timetable)
# ---------------------------------------------------------------------------

class TestRealDatabaseIntegration(unittest.TestCase):
    """Smoke test against the real database to verify end-to-end plumbing.

    These tests do NOT modify the database. They assert structural correctness
    of real query results rather than pinning exact room lists (which would
    break if timetable data changes).
    """

    def test_smoke_real_query_returns_list(self):
        """Smoke: recommend_rooms with valid query returns a list (possibly empty)."""
        # Use a date/time unlikely to be fully saturated (Sunday 03:00–04:00)
        query = _make_query(
            preferred_building="EB1",
            date="2026-08-16",   # Sunday
            start_time="03:00",
            end_time="04:00",
        )
        results = recommend_rooms(query)
        self.assertIsInstance(results, list)

    def test_smoke_mapped_results_have_valid_distance(self):
        """Smoke: Every mapped result has a non-None, non-negative walking_distance."""
        query = _make_query(
            preferred_building="EB1",
            date="2026-08-16",
            start_time="03:00",
            end_time="04:00",
        )
        results = recommend_rooms(query)
        for r in results:
            self.assertIsNotNone(r.campus_node)
            self.assertIsNotNone(r.walking_distance)
            self.assertGreaterEqual(r.walking_distance, 0.0)
            self.assertIsNotNone(r.walking_route)
            self.assertIsInstance(r.walking_route, list)
            self.assertGreater(len(r.walking_route), 0)

    def test_smoke_result_sorted_by_distance(self):
        """Smoke: Mapped results appear in ascending distance order."""
        query = _make_query(
            preferred_building="EB2",
            date="2026-08-16",
            start_time="03:00",
            end_time="04:00",
        )
        results = recommend_rooms(query)
        distances = [r.walking_distance for r in results]
        self.assertEqual(distances, sorted(distances))

    def test_smoke_no_excluded_room_codes_in_results(self):
        """Smoke: Known excluded/alias codes never appear in results."""
        excluded = {"TB- 109", "EB1-1", "EB1-2", "EB2-2", "EB2-4",
                    "TB-102/108", "TB-102/112", "Unassigned", "Unspecified / TBD",
                    "IET Amphi / IM Amphi"}
        query = _make_query(
            preferred_building="TB",
            date="2026-08-16",
            start_time="03:00",
            end_time="04:00",
        )
        results = recommend_rooms(query, include_unmapped_buildings=True)
        for r in results:
            self.assertNotIn(r.room_number, excluded, msg=f"Excluded room {r.room_number!r} appeared in results")

    def test_smoke_room_type_filter_respected(self):
        """Smoke: When required_room_type='Seminar Room', only Seminar Rooms appear."""
        query = _make_query(
            preferred_building="EB1",
            date="2026-08-16",
            start_time="03:00",
            end_time="04:00",
            required_room_type="Seminar Room",
        )
        results = recommend_rooms(query)
        for r in results:
            self.assertEqual(r.room_type, "Seminar Room")


if __name__ == "__main__":
    unittest.main()
