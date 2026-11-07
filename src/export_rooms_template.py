"""Export rooms metadata template CSV.

This script reads the existing ``rooms`` table and creates a CSV file with a
header that includes the new metadata columns (``room_type``, ``equipment`` and
``notes``).  All existing records are written with their current values; the
metadata columns are left empty so that they can be filled in manually later.

The generated file is written to ``data/rooms_metadata_template.csv`` relative
to the project root.
"""

import csv
import pathlib
import sqlite3

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "room_finder.db"
OUTPUT_CSV = PROJECT_ROOT / "data" / "rooms_metadata_template.csv"

def export_rooms_template() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM rooms ORDER BY room_id")
    rows = cur.fetchall()
    if not rows:
        print("No rooms found in the database.")
        return
    # Determine header order – keep original columns then new metadata cols
    fieldnames = [
        "room_id",
        "room_number",
        "building",
        "capacity",
        "room_type",
        "equipment",
        "notes",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # Fill missing metadata columns with empty strings
            writer.writerow(
                {
                    "room_id": row["room_id"],
                    "room_number": row["room_number"],
                    "building": row["building"],
                    "capacity": row["capacity"],
                    "room_type": row["room_type"] if "room_type" in row.keys() else "",
                    "equipment": row["equipment"] if "equipment" in row.keys() else "",
                    "notes": row["notes"] if "notes" in row.keys() else "",
                }
            )
    print(f"Rooms metadata template written to {OUTPUT_CSV}")

if __name__ == "__main__":
    export_rooms_template()

