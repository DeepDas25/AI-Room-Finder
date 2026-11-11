"""Unit tests for Campus Building Mapping Rules."""

import unittest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.building_mapper import get_campus_node


class TestBuildingMapper(unittest.TestCase):

    def test_standard_prefixes(self):
        """Standard prefixes map cleanly to their primary campus nodes."""
        self.assertEqual(get_campus_node("EB1-101"), "EB1")
        self.assertEqual(get_campus_node("EB1-002"), "EB1")
        self.assertEqual(get_campus_node("EB2-104"), "EB2")
        self.assertEqual(get_campus_node("EB2-001"), "EB2")
        self.assertEqual(get_campus_node("TB-102"), "TB")
        self.assertEqual(get_campus_node("TB-109"), "TB")
        self.assertEqual(get_campus_node("IM-102"), "IM")
        self.assertEqual(get_campus_node("IM-106"), "IM")

    def test_aic_maps_to_eb2(self):
        """Any room starting with AIC must map to EB2."""
        self.assertEqual(get_campus_node("AIC-004"), "EB2")
        self.assertEqual(get_campus_node("AIC-004", "Atal Incubation Centre (AIC)"), "EB2")
        self.assertEqual(get_campus_node("AIC-101"), "EB2")

    def test_eb006_and_iet_amphitheatre_map_to_eb1(self):
        """EB-006, EB-006 (IET), and IET Amphitheatre map to EB1."""
        self.assertEqual(get_campus_node("EB-006"), "EB1")
        self.assertEqual(get_campus_node("EB-006 (IET)"), "EB1")
        self.assertEqual(get_campus_node("EB-006 (IET)", "Engineering Block (EB)"), "EB1")
        self.assertEqual(get_campus_node("IET Amphitheatre"), "EB1")
        self.assertEqual(get_campus_node("IET Amphitheatre", "Campus Amphitheatres"), "EB1")

    def test_engineering_block_eb_special_case(self):
        """Database building 'Engineering Block (EB)' maps to EB1."""
        self.assertEqual(get_campus_node("UNKNOWN_ROOM", "Engineering Block (EB)"), "EB1")

    def test_im_amphitheatre_maps_to_im(self):
        """IM Amphitheatre maps to IM."""
        self.assertEqual(get_campus_node("IM Amphitheatre"), "IM")
        self.assertEqual(get_campus_node("IM Amphitheatre", "Campus Amphitheatres"), "IM")

    def test_byod_and_technology_block_computer_labs_map_to_tb(self):
        """BYOD and Computer Science Labs in Technology Block map to TB."""
        self.assertEqual(get_campus_node("BYOD"), "TB")
        self.assertEqual(get_campus_node("BYOD", "Computer Science Labs"), "TB")
        self.assertEqual(get_campus_node("CS-LAB-1", "Computer Science Labs"), "TB")

    def test_lrc_computer_labs_strictly_remain_unmapped(self):
        """LRC002 and LRC007 must strictly return None, taking precedence over generic lab rules."""
        self.assertIsNone(get_campus_node("LRC002"))
        self.assertIsNone(get_campus_node("LRC002", "Learning Resource Centre (LRC)"))
        self.assertIsNone(get_campus_node("LRC007"))
        self.assertIsNone(get_campus_node("LRC007", "Learning Resource Centre (LRC)"))
        # Explicit test of LRC precedence over Computer Science Labs building
        self.assertIsNone(get_campus_node("LRC002", "Computer Science Labs"))
        self.assertIsNone(get_campus_node("LRC007", "Computer Science Labs"))
        self.assertIsNone(get_campus_node("LRC-ANY", "Computer Science Labs"))

    def test_unconfirmed_specialized_locations_remain_unmapped(self):
        """Unconfirmed specialized locations must return None without guessing."""
        self.assertIsNone(get_campus_node("LRC002"))
        self.assertIsNone(get_campus_node("LRC002", "Learning Resource Centre (LRC)"))
        self.assertIsNone(get_campus_node("LRC007", "Learning Resource Centre (LRC)"))
        self.assertIsNone(get_campus_node("Unassigned", "Unassigned"))
        self.assertIsNone(get_campus_node("", ""))
        self.assertIsNone(get_campus_node("RANDOM_ROOM", "UNKNOWN_BUILDING"))


if __name__ == "__main__":
    unittest.main()

