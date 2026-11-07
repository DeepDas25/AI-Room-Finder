"""Verification script for the imported data.

- Prints row counts for the three tables.
- Executes a sample room‑availability query: list distinct rooms that have a class on Monday at 09:00.
"""
import pathlib
import sqlite3

BASE_DIR = pathlib.Path(r"C:/Users/deepa/OneDrive/Desktop/AI_project")
DB_PATH = BASE_DIR / "data" / "room_finder.db"

def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    for table in ("rooms", "timetable_entries", "source_files"):
        cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
        cnt = cur.fetchone()["cnt"]
        print(f"{table}: {cnt} rows")

    # Sample room‑availability query
    print("\nSample query: rooms with a class on Monday at 09:00")
    cur.execute(
        """
        SELECT DISTINCT room_number
        FROM timetable_entries
        WHERE day = 'Monday' AND start_time = '09:00'
        ORDER BY room_number;
        """
    )
    rooms = [row["room_number"] for row in cur.fetchall()]
    print("Rooms:", ", ".join(rooms) if rooms else "(none)")
    conn.close()

if __name__ == "__main__":
    main()

