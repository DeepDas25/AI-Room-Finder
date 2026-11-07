"""Utility script to report counts for the approved dataset.
It prints:
- Total approved timetable entries
- Total unresolved visiting faculty entries
- Total unique rooms in the approved inventory
"""
import csv
import pathlib

BASE = pathlib.Path(r"C:/Users/deepa/OneDrive/Desktop/AI_project")
DATA = BASE / "data" / "processed"

APPROVED = DATA / "all_timetable_entries_approved.csv"
UNRESOLVED = DATA / "visiting_faculty_unresolved.csv"
UNIQUE_ROOMS = DATA / "unique_rooms_approved.csv"

def count_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # subtract header

print("Approved timetable entries:", count_rows(APPROVED))
print("Unresolved visiting faculty entries:", count_rows(UNRESOLVED))
print("Unique rooms (approved):", count_rows(UNIQUE_ROOMS))

