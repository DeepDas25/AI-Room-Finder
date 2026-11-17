"""Unit tests for the Natural Language Search Assistant (src/nlp_assistant.py).

Tests are designed to be completely deterministic by injecting fixed
reference datetimes.
"""

import datetime
import pathlib
import sys
import unittest

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.nlp_assistant import (
    process_natural_language_request,
    NLPResponse,
    _extract_capacity,
    _extract_room_type,
    _extract_equipment,
    _extract_buildings,
    _extract_date,
    _extract_times,
)


class TestNLPAssistant(unittest.TestCase):
    """Unit test suite for NLP Search Assistant."""

    def setUp(self):
        # Anchor datetime: Wednesday, 2026-11-18 at 10:00 AM
        self.ref_now = datetime.datetime(2026, 11, 18, 10, 0, 0)

    # -----------------------------------------------------------------------
    # 1. Core Chatbot Behaviors
    # -----------------------------------------------------------------------

    def test_behavior_a_general_search_now(self):
        """A. General search: 'Find an empty room now.' -> all buildings, 60m window."""
        res = process_natural_language_request("Find an empty room now.", reference_now=self.ref_now)
        self.assertEqual(res.status, "SUCCESS")
        self.assertIsNotNone(res.query)
        self.assertIsNone(res.query.preferred_building)
        self.assertIsNone(res.query.filter_building)
        self.assertEqual(res.query.date, "2026-11-18")
        self.assertEqual(res.query.start_time, "10:00")
        self.assertEqual(res.query.end_time, "11:00")
        self.assertEqual(res.query.min_capacity, 0)
        self.assertIsInstance(res.recommendations, list)
        self.assertGreater(len(res.recommendations), 0)
        # All walking_distance must be None (no distance bias)
        self.assertTrue(all(r.walking_distance is None for r in res.recommendations))

    def test_behavior_b_specific_building(self):
        """B. Specific building: 'Find an empty room in EB2.' -> filter_building='EB2'."""
        res = process_natural_language_request("Find an empty room in EB2.", reference_now=self.ref_now)
        self.assertEqual(res.status, "SUCCESS")
        self.assertIsNotNone(res.query)
        self.assertEqual(res.query.filter_building, "EB2")
        self.assertIsNone(res.query.preferred_building)
        self.assertTrue(all(r.campus_node == "EB2" for r in res.recommendations))

    def test_behavior_c_ambiguous_building_clarification(self):
        """C. Ambiguous building: 'Find an empty room in this building.' -> NEEDS_CLARIFICATION."""
        queries = [
            "Find an empty room in this building.",
            "Is there a room available here?",
            "Book a class in my building.",
            "Find a classroom in this building tomorrow at 2 PM.",
        ]
        for q in queries:
            res = process_natural_language_request(q, reference_now=self.ref_now)
            self.assertEqual(res.status, "NEEDS_CLARIFICATION", msg=f"Failed for query: {q}")
            self.assertEqual(res.clarification_prompt, "Which building are you referring to?")
            self.assertEqual(res.options, ["EB1", "EB2", "IM", "TB"])
            self.assertEqual(res.recommendations, [])

    def test_behavior_d_nearby_search(self):
        """D. Nearby search: 'Find an empty room near EB2.' -> preferred_building='EB2', all buildings."""
        res = process_natural_language_request("Find an empty room near EB2.", reference_now=self.ref_now)
        self.assertEqual(res.status, "SUCCESS")
        self.assertIsNotNone(res.query)
        self.assertEqual(res.query.preferred_building, "EB2")
        self.assertIsNone(res.query.filter_building)
        self.assertGreater(len(res.recommendations), 0)
        # First room must be in EB2 with distance 0.0
        self.assertEqual(res.recommendations[0].campus_node, "EB2")
        self.assertEqual(res.recommendations[0].walking_distance, 0.0)
        # Distances should be sorted ascending
        dists = [r.walking_distance for r in res.recommendations if r.walking_distance is not None]
        self.assertEqual(dists, sorted(dists))

    def test_behavior_e_detailed_search(self):
        """E. Detailed search: classroom, 40 students, in EB2, tomorrow 2 to 3, with projector."""
        text = "Find a classroom for 40 students in EB2 tomorrow from 2 to 3 with a projector."
        res = process_natural_language_request(text, reference_now=self.ref_now)
        self.assertEqual(res.status, "SUCCESS")
        self.assertIsNotNone(res.query)
        self.assertEqual(res.query.filter_building, "EB2")
        self.assertEqual(res.query.required_room_type, "Classroom")
        self.assertEqual(res.query.min_capacity, 40)
        self.assertEqual(res.query.date, "2026-11-19")   # tomorrow
        self.assertEqual(res.query.start_time, "14:00")  # 2 PM
        self.assertEqual(res.query.end_time, "15:00")    # 3 PM
        self.assertIn("Projector", res.query.required_equipment)
        # Results should be verified
        self.assertTrue(all(r.campus_node == "EB2" for r in res.recommendations))
        self.assertTrue(all(r.capacity >= 40 for r in res.recommendations))
        self.assertTrue(all(r.room_type == "Classroom" for r in res.recommendations))

    # -----------------------------------------------------------------------
    # 2. Building Synonyms and Intent Distinction
    # -----------------------------------------------------------------------

    def test_building_synonyms(self):
        """Building synonyms map to canonical nodes EB1, EB2, TB, IM."""
        synonym_cases = [
            ("in Engineering Block 1", "EB1", None),
            ("in EB-1", "EB1", None),
            ("near Engineering Block 2", None, "EB2"),
            ("in Tech Block", "TB", None),
            ("close to Technology Block", None, "TB"),
            ("in CS Labs", "TB", None),
            ("at Management Block", "IM", None),
            ("near Institute of Management", None, "IM"),
            ("in AIC", "EB2", None),
        ]
        for phrase, expected_filter, expected_pref in synonym_cases:
            fb, pb = _extract_buildings(phrase)
            self.assertEqual(fb, expected_filter, msg=f"Filter mismatch for: {phrase}")
            self.assertEqual(pb, expected_pref, msg=f"Pref mismatch for: {phrase}")

    # -----------------------------------------------------------------------
    # 3. Room Type Synonyms
    # -----------------------------------------------------------------------

    def test_room_type_synonyms(self):
        """Room type synonyms map to Classroom, Computer Lab, Seminar Room."""
        cases = [
            ("Need a classroom for tomorrow", "Classroom"),
            ("Find a lecture hall", "Classroom"),
            ("Need a class", "Classroom"),
            ("Reserve a computer lab", "Computer Lab"),
            ("Find a pc lab", "Computer Lab"),
            ("Need a systems lab", "Computer Lab"),
            ("Looking for a lab", "Computer Lab"),
            ("Need a seminar room", "Seminar Room"),
            ("Find a conference room", "Seminar Room"),
            ("Need a room", None),
        ]
        for phrase, expected in cases:
            self.assertEqual(_extract_room_type(phrase), expected, msg=f"Failed for: {phrase}")

    # -----------------------------------------------------------------------
    # 4. Equipment Synonyms
    # -----------------------------------------------------------------------

    def test_equipment_synonyms(self):
        """Equipment terms map to AC, Computers, Power sockets, Projector, Smartboard, Wi-Fi."""
        cases = [
            ("with a projector and smartboard", ("Projector", "Smartboard")),
            ("needs ac and wifi", ("AC", "Wi-Fi")),
            ("must have computers and power sockets", ("Computers", "Power sockets")),
            ("with charging points and air conditioning", ("AC", "Power sockets")),
            ("with screen and wireless", ("Projector", "Wi-Fi")),
        ]
        for phrase, expected in cases:
            res = _extract_equipment(phrase)
            for item in expected:
                self.assertIn(item, res, msg=f"Missing {item} for '{phrase}'")

    # -----------------------------------------------------------------------
    # 5. Capacity Parsing
    # -----------------------------------------------------------------------

    def test_capacity_extraction(self):
        """Capacity expressions correctly extract integer values."""
        cases = [
            ("for 40 students", 40),
            ("capacity of 75", 75),
            ("seats 60", 60),
            ("at least 30 seats", 30),
            ("capacity 100", 100),
            ("holds 25 people", 25),
            ("room for 50", 50),
            ("room with smartboard", 0),
        ]
        for phrase, expected in cases:
            self.assertEqual(_extract_capacity(phrase), expected, msg=f"Failed for: {phrase}")

    # -----------------------------------------------------------------------
    # 6. Date Parsing (Relative and Explicit)
    # -----------------------------------------------------------------------

    def test_date_parsing_relative(self):
        """Relative date tokens (today, tomorrow, weekday names)."""
        # Ref: Wed 2026-11-18
        self.assertEqual(_extract_date("today", self.ref_now)[0], "2026-11-18")
        self.assertEqual(_extract_date("tomorrow", self.ref_now)[0], "2026-11-19")
        # This Friday (2 days ahead)
        self.assertEqual(_extract_date("this Friday", self.ref_now)[0], "2026-11-20")
        # Next Friday (2 + 7 = 9 days ahead -> 2026-11-27)
        self.assertEqual(_extract_date("next Friday", self.ref_now)[0], "2026-11-27")
        # Next Monday (5 + 7 = 12 days ahead -> 2026-11-30)
        self.assertEqual(_extract_date("next Monday", self.ref_now)[0], "2026-11-30")

    def test_date_parsing_explicit(self):
        """Explicit dates in ISO, DMY, and month name formats."""
        self.assertEqual(_extract_date("on 2026-12-05", self.ref_now)[0], "2026-12-05")
        self.assertEqual(_extract_date("on 25/12/2026", self.ref_now)[0], "2026-12-25")
        self.assertEqual(_extract_date("on 15th December 2026", self.ref_now)[0], "2026-12-15")
        self.assertEqual(_extract_date("November 22", self.ref_now)[0], "2026-11-22")

    # -----------------------------------------------------------------------
    # 7. Time Parsing & University Context Shorthand
    # -----------------------------------------------------------------------

    def test_university_time_shorthand(self):
        """University shorthand (2 to 3 -> 14:00-15:00, 10 to 12 -> 10:00-12:00)."""
        cases = [
            ("from 2 to 3", ("14:00", "15:00")),
            ("2 to 3", ("14:00", "15:00")),
            ("from 10 to 12", ("10:00", "12:00")),
            ("9 to 11", ("09:00", "11:00")),
            ("1 to 2", ("13:00", "14:00")),
            ("from 2pm to 3pm", ("14:00", "15:00")),
            ("from 10am to 11am", ("10:00", "11:00")),
            ("from 11 to 1pm", ("11:00", "13:00")),
            ("from 14:00 to 15:30", ("14:00", "15:30")),
        ]
        for phrase, expected in cases:
            st, et = _extract_times(phrase, self.ref_now)
            self.assertEqual((st, et), expected, msg=f"Failed for: {phrase}")

    def test_duration_parsing(self):
        """Duration expressions: 'at 2 PM for 1 hour', 'at 10:00 for 50 minutes'."""
        st, et = _extract_times("at 2 PM for 1 hour", self.ref_now)
        self.assertEqual((st, et), ("14:00", "15:00"))

        st, et = _extract_times("at 10:00 for 50 minutes", self.ref_now)
        self.assertEqual((st, et), ("10:00", "10:50"))

        st, et = _extract_times("at 2 for 2 hours", self.ref_now)
        self.assertEqual((st, et), ("14:00", "16:00"))

    # -----------------------------------------------------------------------
    # 8. Error and Edge Cases
    # -----------------------------------------------------------------------

    def test_empty_input(self):
        """Empty input returns ERROR status."""
        res = process_natural_language_request("")
        self.assertEqual(res.status, "ERROR")
        self.assertIn("empty", res.error_message.lower())

        res2 = process_natural_language_request("   ")
        self.assertEqual(res2.status, "ERROR")

    def test_invalid_time_interval_rejected(self):
        """Start time >= end time returns ERROR."""
        # e.g. "from 3 PM to 2 PM" -> start 15:00, end 14:00
        res = process_natural_language_request("Find a room from 3 PM to 2 PM today.", reference_now=self.ref_now)
        self.assertEqual(res.status, "ERROR")
        self.assertIn("earlier than end_time", res.error_message)

    def test_required_regression_cases(self):
        """Test all 8 required regression test cases for input validation and error handling."""
        cases = [
            ("Find a room at 25 PM", "hour"),
            ("Find a room at 13 PM", "hour"),
            ("Find a room at 25:00", "hour"),
            ("Find a room at 10:75", "minute"),
            ("Find a room for -2 hours", "positive"),
            ("Find a room for 0 minutes", "positive"),
            ("Find a room on 2026-99-45", "date"),
            ("Find a room from 15 to 10", "earlier than end_time"),
        ]

        for query, expected_snippet in cases:
            res = process_natural_language_request(query, reference_now=self.ref_now)
            self.assertEqual(
                res.status,
                "ERROR",
                msg=f"Expected ERROR for query '{query}', got status '{res.status}'",
            )
            self.assertIsNotNone(res.error_message)
            self.assertIn(
                expected_snippet.lower(),
                res.error_message.lower(),
                msg=f"Snippet '{expected_snippet}' not found in '{res.error_message}' for query '{query}'",
            )
            self.assertEqual(res.recommendations, [])
            if query == "Find a room on 2026-99-45":
                self.assertIsNone(res.query)
                self.assertNotIn("start_time", res.parsed_slots)

    def test_helper_direct_validation_exceptions(self):
        """Verify helper functions raise ValueError directly on invalid input."""
        with self.assertRaises(ValueError):
            _extract_times("at 25 PM", self.ref_now)

        with self.assertRaises(ValueError):
            _extract_times("at 13 PM", self.ref_now)

        with self.assertRaises(ValueError):
            _extract_times("at 25:00", self.ref_now)

        with self.assertRaises(ValueError):
            _extract_times("at 10:75", self.ref_now)

        with self.assertRaises(ValueError):
            _extract_times("for -2 hours", self.ref_now)

        with self.assertRaises(ValueError):
            _extract_times("for 0 minutes", self.ref_now)

        with self.assertRaises(ValueError):
            _extract_times("from 15 to 10", self.ref_now)

        with self.assertRaises(ValueError):
            _extract_date("on 2026-99-45", self.ref_now)

    # -----------------------------------------------------------------------
    # 9. Real Database Integration
    # -----------------------------------------------------------------------

    def test_live_recommendation_integration(self):
        """End-to-end integration test querying live database via natural language."""
        query_text = "Find a classroom for 60 students in TB tomorrow from 10 to 11 with smartboard"
        res = process_natural_language_request(query_text, reference_now=self.ref_now)
        self.assertEqual(res.status, "SUCCESS")
        self.assertGreater(len(res.recommendations), 0)
        for r in res.recommendations:
            self.assertEqual(r.campus_node, "TB")
            self.assertEqual(r.room_type, "Classroom")
            self.assertGreaterEqual(r.capacity, 60)
            self.assertIn("Smartboard", r.equipment)


if __name__ == "__main__":
    unittest.main()

