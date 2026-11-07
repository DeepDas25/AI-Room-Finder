"""
Test script for verifying database initialization and table schemas.
-------------------------------------------------------------------
This script:
1. Calls init_database() to create the database and tables.
2. Checks that foreign key constraints are active.
3. Verifies that 'rooms', 'timetable_entries', and 'source_files' exist.
4. Validates table columns and prints verification status.
"""

import sys
from pathlib import Path

# Add project root directory to sys.path so 'src' can be imported easily
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.database import get_connection, init_database, DEFAULT_DB_PATH


def test_database_setup() -> bool:
    print("=" * 60)
    print("Starting Database Foundation Verification Test")
    print("=" * 60)

    # Step 1: Initialize database
    print("\n[Step 1] Initializing database...")
    init_database()

    # Verify that the database file was created on disk
    if not DEFAULT_DB_PATH.exists():
        print(f"[FAIL] Database file not found at: {DEFAULT_DB_PATH}")
        return False
    print(f"[PASS] Database file exists at: {DEFAULT_DB_PATH}")

    # Step 2: Open connection and verify foreign key support
    print("\n[Step 2] Checking SQLite Foreign Key setting...")
    conn = get_connection()
    cursor = conn.cursor()

    fk_status = cursor.execute("PRAGMA foreign_keys;").fetchone()[0]
    if fk_status == 1:
        print("[PASS] Foreign key constraints are ENABLED.")
    else:
        print("[FAIL] Foreign key constraints are DISABLED.")
        conn.close()
        return False

    # Step 3: Verify the three required tables exist
    print("\n[Step 3] Checking required tables...")
    expected_tables = {"rooms", "timetable_entries", "source_files"}
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    existing_tables = {row["name"] for row in cursor.fetchall()}

    all_passed = True
    for table in expected_tables:
        if table in existing_tables:
            print(f"  [PASS] Table '{table}' exists.")
        else:
            print(f"  [FAIL] Table '{table}' is MISSING.")
            all_passed = False

    if not all_passed:
        conn.close()
        return False

    # Step 4: Display column details for each table
    print("\n[Step 4] Verifying table schemas & columns:")
    for table in sorted(expected_tables):
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        col_summary = [f"{col['name']} ({col['type']})" for col in columns]
        print(f"  - {table}: {', '.join(col_summary)}")

    # Step 5: Verify table row counts (ensuring no data is inserted yet)
    print("\n[Step 5] Checking that tables are currently empty:")
    for table in sorted(expected_tables):
        cursor.execute(f"SELECT COUNT(*) as count FROM {table};")
        count = cursor.fetchone()["count"]
        print(f"  - {table}: {count} rows")

    conn.close()

    print("\n" + "=" * 60)
    print("All database foundation tests PASSED successfully!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_database_setup()
    if not success:
        sys.exit(1)

