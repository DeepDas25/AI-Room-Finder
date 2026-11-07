"""Import and update room metadata from CSV into SQLite.

The script is idempotent: running it multiple times will not create duplicate
rooms or change existing non‑metadata fields (e.g., building). It also creates
backups of the database and the source CSV before making any changes.

It generates three reports (saved in the ``data/backup`` directory):
* ``invalid_rooms.txt`` – room codes that are not physical rooms.
* ``alternate_venues.txt`` – rows that represent alternate‑venue notations.
* ``unresolved_venues.txt`` – entries like ``Unassigned`` or ``Unspecified / TBD``.

Usage (from project root):
    python -m src.import_rooms_metadata
"""

import csv
import datetime
import pathlib
import shutil
import sqlite3
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "room_finder.db"
CSV_PATH = DATA_DIR / "rooms_metadata_template.csv"
BACKUP_DIR = DATA_DIR / "backup"

def _ensure_backup_dir() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def _backup_file(src: pathlib.Path, suffix: str) -> pathlib.Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"{src.name}.{timestamp}{suffix}"
    shutil.copy2(src, dst)
    return dst

def _normalize_room_number(room: str) -> str:
    # Remove stray spaces (e.g., "TB- 109" -> "TB-109")
    return room.replace(" ", "").strip()

def import_metadata(csv_path: pathlib.Path = CSV_PATH) -> dict:
    """Read the CSV, update the ``rooms`` table, and write reports.

    Returns a dictionary with counts for reporting.
    """
    # ---------------------------------------------------------------------
    # Backups – must happen before any DB write.
    # ---------------------------------------------------------------------
    _ensure_backup_dir()
    backup_db = _backup_file(DB_PATH, ".bak")
    backup_csv = _backup_file(csv_path, ".bak")

    # Containers for reports
    invalid_rooms = []
    alternate_venues = []
    unresolved_venues = []

    # ---------------------------------------------------------------------
    # Load CSV rows
    # ---------------------------------------------------------------------
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # ---------------------------------------------------------------------
    # Open DB connection
    # ---------------------------------------------------------------------
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Ensure the metadata columns exist (they were added previously)
    # No schema changes here – we only update data.

    for row in rows:
        raw_number = row["room_number"].strip()
        room_number = _normalize_room_number(raw_number)
        notes = (row.get("notes") or "").strip().lower()

        # Classify special rows
        if "invalid code" in notes:
            invalid_rooms.append(room_number)
            continue
        if "alternate venue notation" in notes:
            alternate_venues.append(room_number)
            continue
        if "unresolved venue" in notes:
            unresolved_venues.append(room_number)
            continue

        # Prepare data for UPDATE / INSERT
        capacity = row["capacity"].strip()
        capacity_val = int(capacity) if capacity.isdigit() else None
        room_type = row["room_type"].strip() or None
        equipment = row["equipment"].strip() or None
        notes_val = (row.get("notes") or "").strip() or None

        # Check if a room with this normalized number already exists
        cur.execute(
            "SELECT room_id FROM rooms WHERE REPLACE(room_number, ' ', '') = ?",
            (room_number,),
        )
        existing = cur.fetchone()
        if existing:
            # UPDATE existing record – keep building unchanged
            cur.execute(
                """
                UPDATE rooms
                SET capacity = ?, room_type = ?, equipment = ?, notes = ?
                WHERE room_id = ?
                """,
                (capacity_val, room_type, equipment, notes_val, existing["room_id"]),
            )
        else:
            # INSERT new physical room – use the CSV's room_id if possible
            # (room_id from CSV may be None for alternate/invalid rows, which we skip)
            csv_room_id = row["room_id"].strip()
            room_id_val = int(csv_room_id) if csv_room_id.isdigit() else None
            # Need building – use what CSV provides.
            building = row["building"].strip()
            cur.execute(
                """
                INSERT INTO rooms (room_id, room_number, building, capacity, room_type, equipment, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    room_id_val,
                    room_number,
                    building,
                    capacity_val,
                    room_type,
                    equipment,
                    notes_val,
                ),
            )
    conn.commit()
    conn.close()

    # ---------------------------------------------------------------------
    # Write reports
    # ---------------------------------------------------------------------
    def _write_report(name: str, items: list) -> pathlib.Path:
        report_path = BACKUP_DIR / f"{name}.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            for i in items:
                f.write(i + "\n")
        return report_path

    _write_report("invalid_rooms", invalid_rooms)
    _write_report("alternate_venues", alternate_venues)
    _write_report("unresolved_venues", unresolved_venues)

    return {
        "backup_db": backup_db,
        "backup_csv": backup_csv,
        "invalid_count": len(invalid_rooms),
        "alternate_count": len(alternate_venues),
        "unresolved_count": len(unresolved_venues),
        "rooms_updated": len(rows) - len(invalid_rooms) - len(alternate_venues) - len(unresolved_venues),
    }

if __name__ == "__main__":
    result = import_metadata()
    print("Import completed. Summary:")
    for k, v in result.items():
        print(f"{k}: {v}")
