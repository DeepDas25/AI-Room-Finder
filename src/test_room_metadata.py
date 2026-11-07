"""Tests for the room metadata columns and CSV export."""

import csv
import pathlib
import sqlite3
import subprocess
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "room_finder.db"
CSV_PATH = PROJECT_ROOT / "data" / "rooms_metadata_template.csv"
SCRIPT_PATH = PROJECT_ROOT / "src" / "export_rooms_template.py"


class TestRoomMetadata(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()

    def tearDown(self):
        self.conn.close()

    def test_columns_exist(self):
        """The three new metadata columns must be present in the rooms table."""
        self.cur.execute("PRAGMA table_info(rooms)")
        cols = {row[1] for row in self.cur.fetchall()}
        for col in ["room_type", "equipment", "notes"]:
            self.assertIn(col, cols, f"Column '{col}' should exist in rooms table.")

    def test_physical_rooms_have_metadata(self):
        """Every room that is a known physical venue must have room_type and equipment filled."""
        # Physical rooms are those where room_type IS NOT NULL
        self.cur.execute(
            "SELECT room_number, room_type, equipment FROM rooms WHERE room_type IS NOT NULL"
        )
        rows = self.cur.fetchall()
        self.assertGreater(len(rows), 0, "At least some rooms should have metadata.")
        for row in rows:
            self.assertIsNotNone(
                row["room_type"],
                f"Room {row['room_number']} has NULL room_type but should have a type."
            )
            self.assertIsNotNone(
                row["equipment"],
                f"Room {row['room_number']} has NULL equipment but should have equipment listed."
            )

    def test_invalid_codes_have_no_metadata(self):
        """EB1-1, EB1-2, EB2-2, EB2-4 are invalid codes and must have NULL metadata."""
        invalid_codes = ["EB1-1", "EB1-2", "EB2-2", "EB2-4"]
        for code in invalid_codes:
            self.cur.execute(
                "SELECT room_type, equipment FROM rooms WHERE room_number=?", (code,)
            )
            row = self.cur.fetchone()
            if row is not None:
                self.assertIsNone(
                    row["room_type"],
                    f"Invalid code {code} should have NULL room_type."
                )

    def test_byod_is_computer_lab(self):
        """BYOD must be classified as a Computer Lab with capacity 60."""
        self.cur.execute(
            "SELECT room_type, capacity FROM rooms WHERE room_number='BYOD'"
        )
        row = self.cur.fetchone()
        self.assertIsNotNone(row, "BYOD must exist in the rooms table.")
        self.assertEqual(row["room_type"], "Computer Lab")
        self.assertEqual(row["capacity"], 60)

    def test_amphitheatres_are_separate(self):
        """IET Amphitheatre and IM Amphitheatre must be separate rooms, each with capacity 100."""
        for name in ["IET Amphitheatre", "IM Amphitheatre"]:
            self.cur.execute(
                "SELECT room_type, capacity FROM rooms WHERE room_number=?", (name,)
            )
            row = self.cur.fetchone()
            self.assertIsNotNone(row, f"'{name}' must exist as a separate room.")
            self.assertEqual(row["capacity"], 100, f"'{name}' should have capacity 100.")
            self.assertEqual(row["room_type"], "Seminar Room")

    def test_tb109_no_duplicate(self):
        """TB- 109 (spaced) and TB-109 should not both have metadata – only one is canonical."""
        self.cur.execute(
            "SELECT room_number, room_type FROM rooms WHERE room_number IN ('TB-109', 'TB- 109')"
        )
        rows = self.cur.fetchall()
        # At most one of them should have metadata (room_type not NULL)
        with_meta = [r for r in rows if r["room_type"] is not None]
        self.assertLessEqual(
            len(with_meta), 1,
            "Only one of 'TB-109'/'TB- 109' should have metadata; the other should be NULL."
        )

    def test_csv_template_generated(self):
        """Running export_rooms_template.py should produce a CSV with correct header and row count."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True, text=True
        )
        self.assertEqual(
            result.returncode, 0,
            f"export_rooms_template.py failed:\n{result.stderr}"
        )
        self.assertTrue(CSV_PATH.is_file(), "CSV template file should exist after running script.")
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        expected = ["room_id", "room_number", "building", "capacity", "room_type", "equipment", "notes"]
        self.assertEqual(header, expected, "CSV header should match expected columns.")
        # Row count must equal total rooms in DB
        self.cur.execute("SELECT COUNT(*) FROM rooms")
        (db_count,) = self.cur.fetchone()
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            csv_rows = sum(1 for _ in csv.reader(f)) - 1  # subtract header
        self.assertEqual(csv_rows, db_count, "CSV row count should match rooms table count.")


if __name__ == "__main__":
    unittest.main()
