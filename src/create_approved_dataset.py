# create_approved_dataset.py
"""Script to generate the approved timetable dataset.

- Excludes the two Visiting Faculty entries (IDs 613 and 614).
- Resolves the date‑dependent FinTech entries (IDs 516 and 549) into two explicit rows each:
  * 2026‑08‑03 to 2026‑08‑31 → IET Amphitheatre
  * 2026‑09‑01 to 2026‑12‑15 → IM Amphitheatre
- Writes the approved CSV, a separate CSV for the unresolved Visiting Faculty rows,
  and updates the room inventory to include a distinct "IM Amphitheatre" entry.
"""

import csv
import pathlib

# Paths (project root is the working directory)
BASE_DIR = pathlib.Path(r"C:/Users/deepa/OneDrive/Desktop/AI_project")
DATA_DIR = BASE_DIR / "data" / "processed"

ALL_PATH = DATA_DIR / "all_timetable_entries_with_sem5.csv"
APPROVED_PATH = DATA_DIR / "all_timetable_entries_approved.csv"
UNRESOLVED_VISITING_PATH = DATA_DIR / "visiting_faculty_unresolved.csv"
UNIQUE_ROOMS_PATH = DATA_DIR / "unique_rooms_with_sem5.csv"
UPDATED_ROOMS_PATH = DATA_DIR / "unique_rooms_approved.csv"

# IDs to handle
VISITING_IDS = {"613", "614"}
FINTECH_IDS = {"516", "549"}

def split_fintech(row, start_date, end_date, venue):
    new_row = row.copy()
    new_row["actual_room"] = venue
    new_row["effective_start_date"] = start_date
    new_row["effective_end_date"] = end_date
    new_row["needs_verification"] = "False"
    # keep other fields unchanged
    return new_row

def main():
    approved_rows = []
    visiting_rows = []

    with open(ALL_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            eid = row["entry_id"]
            if eid in VISITING_IDS:
                visiting_rows.append(row)
                continue
            if eid in FINTECH_IDS:
                # First period – IET Amphitheatre (03 Aug – 31 Aug)
                approved_rows.append(
                    split_fintech(
                        row,
                        start_date="2026-08-03",
                        end_date="2026-08-31",
                        venue="IET Amphitheatre",
                    )
                )
                # Second period – IM Amphitheatre (01 Sep – 15 Dec)
                approved_rows.append(
                    split_fintech(
                        row,
                        start_date="2026-09-01",
                        end_date="2026-12-15",
                        venue="IM Amphitheatre",
                    )
                )
                continue
            # All other rows stay unchanged
            approved_rows.append(row)

    # Write approved dataset
    with open(APPROVED_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(approved_rows)

    # Write unresolved visiting faculty rows
    with open(UNRESOLVED_VISITING_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(visiting_rows)

    # Update unique rooms inventory – copy existing and add IM Amphitheatre if missing
    rooms = []
    existing_codes = set()
    with open(UNIQUE_ROOMS_PATH, newline="", encoding="utf-8") as f:
        r_reader = csv.DictReader(f)
        room_fields = r_reader.fieldnames
        for r in r_reader:
            rooms.append(r)
            existing_codes.add(r["room_code"].strip())

    if "IM Amphitheatre" not in existing_codes:
        rooms.append({
            "room_code": "IM Amphitheatre",
            "building": "Campus Amphitheatres",
            "room_type": "Open Amphitheatre / Auditorium",
            "is_regular_classroom": "False",
            "is_alternate_venue": "True",
            "total_scheduled_slots": "2",
            "source_files": "Time_Table_Final IM V.4 from 3-Aug-26.pdf",
        })

    with open(UPDATED_ROOMS_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=room_fields)
        w.writeheader()
        w.writerows(rooms)

if __name__ == "__main__":
    main()

