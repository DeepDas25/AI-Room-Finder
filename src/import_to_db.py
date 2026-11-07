"""Import approved CSV data into the SQLite database.

- Inserts rooms from `unique_rooms_approved.csv` into the `rooms` table.
- Inserts approved timetable entries from `all_timetable_entries_approved.csv` into `timetable_entries`.
- Adds extra columns to `timetable_entries` if they are missing (effective dates, schedule_type, duration_minutes, notes, needs_verification, verification_reason, is_alternate_venue).
- Uses `INSERT OR IGNORE` for rooms and omits the source `entry_id` so that SQLite assigns its own primary key, avoiding duplicate‑key issues when date‑dependent rows were split.
- The script is idempotent – running it again will not create duplicate rows.
"""

import csv
import pathlib
import sqlite3

# Project paths
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"

DB_PATH = BASE_DIR / "data" / "room_finder.db"

# CSV files
ROOMS_CSV = DATA_DIR / "unique_rooms_approved.csv"
TIMETABLE_CSV = DATA_DIR / "all_timetable_entries_approved.csv"
VISITING_CSV = DATA_DIR / "visiting_faculty_unresolved.csv"  # not used for import, just documented

# ---------------------------------------------------------------------------
# Helper to ensure extra columns exist in timetable_entries
# ---------------------------------------------------------------------------
EXTRA_COLUMNS = [
    ("regular_classroom", "TEXT"),
    ("effective_start_date", "TEXT"),
    ("effective_end_date", "TEXT"),
    ("schedule_type", "TEXT"),
    ("duration_minutes", "INTEGER"),
    ("notes", "TEXT"),
    ("needs_verification", "INTEGER"),  # store as 0/1
    ("verification_reason", "TEXT"),
    ("is_alternate_venue", "INTEGER"),
]


def ensure_extra_columns(conn: sqlite3.Connection):
    cursor = conn.cursor()
    # Get existing columns
    cursor.execute("PRAGMA table_info(timetable_entries);")
    existing = {row[1] for row in cursor.fetchall()}
    for col_name, col_type in EXTRA_COLUMNS:
        if col_name not in existing:
            cursor.execute(
                f"ALTER TABLE timetable_entries ADD COLUMN {col_name} {col_type};"
            )
    conn.commit()


def import_rooms(conn: sqlite3.Connection):
    with open(ROOMS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            # Map CSV columns to rooms table columns
            room_number = r["room_code"].strip()
            building = r["building"].strip()
            # Capacity is not present; keep NULL
            rows.append((room_number, building, None))
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT OR IGNORE INTO rooms (room_number, building, capacity) VALUES (?, ?, ?);",
        rows,
    )
    conn.commit()
    print(f"Inserted/kept {cursor.rowcount} room rows (duplicates ignored).")


def import_timetable(conn: sqlite3.Connection):
    with open(TIMETABLE_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            # Skip any rows that belong to the unresolved visiting faculty file – they are not present here
            # Use the actual venue as the foreign‑key room_number
            room_number = r["actual_room"].strip()
            department = r["department"].strip()
            semester = r["semester"].strip()
            section = r["section"].strip()
            subject = r["subject"].strip()
            day = r["day"].strip()
            start_time = r["start_time"].strip()
            end_time = r["end_time"].strip()
            source_file = r["source_file"].strip()
            # Optional extra fields – may be empty strings
            effective_start = r.get("effective_start_date", "").strip() or None
            effective_end = r.get("effective_end_date", "").strip() or None
            schedule_type = r.get("schedule_type", "").strip() or None
            duration = r.get("duration_minutes", "").strip()
            duration = int(duration) if duration.isdigit() else None
            notes = r.get("notes", "").strip() or None
            needs_ver = r.get("needs_verification", "").strip()
            needs_ver = 1 if needs_ver.lower() == "true" else 0
            ver_reason = r.get("verification_reason", "").strip() or None
            is_alt = r.get("is_alternate_venue", "").strip()
            is_alt = 1 if is_alt.lower() == "true" else 0

            rows.append(
                (
                    room_number,
                    department,
                    semester,
                    section,
                    subject,
                    day,
                    start_time,
                    end_time,
                    source_file,
                    effective_start,
                    effective_end,
                    schedule_type,
                    duration,
                    notes,
                    needs_ver,
                    ver_reason,
                    is_alt,
                )
            )
    # Build INSERT statement with all columns (excluding the autoincrement entry_id)
    columns = [
        "room_number",
        "department",
        "semester",
        "section",
        "subject",
        "day",
        "start_time",
        "end_time",
        "source_file",
        "effective_start_date",
        "effective_end_date",
        "schedule_type",
        "duration_minutes",
        "notes",
        "needs_verification",
        "verification_reason",
        "is_alternate_venue",
    ]
    placeholders = ",".join(["?" for _ in columns])
    sql = f"INSERT INTO timetable_entries ({', '.join(columns)}) VALUES ({placeholders});"
    cursor = conn.cursor()
    cursor.executemany(sql, rows)
    conn.commit()
    print(f"Inserted {cursor.rowcount} timetable rows.")


def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    # Ensure extra columns exist before insertion
    ensure_extra_columns(conn)
    import_rooms(conn)
    import_timetable(conn)
    conn.close()
    print("Import completed.")

if __name__ == "__main__":
    main()

