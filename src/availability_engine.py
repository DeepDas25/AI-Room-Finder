"""Room Availability Engine

Provides a simple function to query the SQLite database for rooms that are free
during a specific date and time window, respecting effective date ranges and
overlap rules.

Usage example::

    from src.availability_engine import find_available_rooms
    rooms = find_available_rooms(
        date_str="2026-08-10",
        start_time="15:00",
        end_time="15:50",
        min_capacity=0,
    )
    for r in rooms:
        print(r)
"""

import datetime
import pathlib
import sqlite3
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Configuration – paths to the database (project root is two levels up)
# ---------------------------------------------------------------------------
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "room_finder.db"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> datetime.date:
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception as exc:
        raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD.") from exc


def _parse_time(time_str: str) -> datetime.time:
    try:
        return datetime.datetime.strptime(time_str, "%H:%M").time()
    except Exception as exc:
        raise ValueError(f"Invalid time format '{time_str}'. Expected HH:MM (24‑hour).") from exc


def _weekday_name(dt: datetime.date) -> str:
    """Return weekday name matching the values stored in the CSV (e.g., 'Monday')."""
    return dt.strftime("%A")

# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def find_available_rooms(
    date_str: str,
    start_time_str: str,
    end_time_str: str,
    min_capacity: int = 0,
) -> List[Dict[str, Any]]:
    """Return a list of rooms that are completely free for the given window.

    Parameters
    ----------
    date_str: ``YYYY-MM-DD``
        Calendar date for the query.
    start_time_str, end_time_str: ``HH:MM`` (24‑hour)
        Desired time interval. ``end_time`` must be later than ``start_time``.
    min_capacity: int, optional
        Minimum required capacity. Rooms with ``NULL`` capacity are treated as
        having unknown capacity and are included when ``min_capacity`` is ``0``.

    Returns
    -------
    List[Dict]
        Each dict contains ``room_number``, ``building`` and ``capacity``.
    """
    # -------------------------------------------------------------------
    # Validate and parse inputs
    # -------------------------------------------------------------------
    request_date = _parse_date(date_str)
    start_time = _parse_time(start_time_str)
    end_time = _parse_time(end_time_str)
    if start_time >= end_time:
        raise ValueError("start_time must be earlier than end_time")
    if min_capacity < 0:
        raise ValueError("min_capacity cannot be negative")

    weekday = _weekday_name(request_date)

    # -------------------------------------------------------------------
    # Connect to DB
    # -------------------------------------------------------------------
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # -------------------------------------------------------------------
    # Base room query – apply capacity filter when possible
    # -------------------------------------------------------------------
    capacity_clause = ""
    params: List[Any] = []
    if min_capacity > 0:
        capacity_clause = "AND (capacity IS NOT NULL AND capacity >= ?)"
        params.append(min_capacity)
    room_query = f"""
        SELECT room_number, building, capacity
        FROM rooms
        WHERE 1=1 {capacity_clause}
    """
    cur.execute(room_query, params)
    all_rooms = [dict(row) for row in cur.fetchall()]

    available_rooms: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------
    # For each room, check for overlapping timetable entries
    # -------------------------------------------------------------------
    for room in all_rooms:
        room_number = room["room_number"]
        overlap_sql = """
            SELECT 1
            FROM timetable_entries
            WHERE room_number = ?
              AND (effective_start_date IS NULL OR effective_start_date <= ?)
              AND (effective_end_date IS NULL OR effective_end_date >= ?)
              AND day = ?
              AND NOT (
                  end_time <= ?   -- existing class ends before our start
                  OR start_time >= ?   -- existing class starts after our end
              )
            LIMIT 1;
        """
        cur.execute(
            overlap_sql,
            (
                room_number,
                request_date.isoformat(),
                request_date.isoformat(),
                weekday,
                start_time_str,
                end_time_str,
            ),
        )
        conflict = cur.fetchone()
        if not conflict:
            available_rooms.append(room)

    conn.close()
    available_rooms.sort(key=lambda r: r["room_number"])
    return available_rooms

# ---------------------------------------------------------------------------
# Simple CLI for manual testing (optional)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 5:
        print("Usage: python availability_engine.py <date> <start> <end> <min_capacity>")
        sys.exit(1)
    date, start, end, cap = sys.argv[1:5]
    rooms = find_available_rooms(date, start, end, int(cap))
    for r in rooms:
        print(r)
