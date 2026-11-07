"""
Database Module for AI Powered Intelligent Room Availability and Finder System
-----------------------------------------------------------------------------
This module handles:
1. SQLite database connection.
2. Enabling foreign key constraints.
3. Initializing required database tables (rooms, timetable_entries, source_files).
"""

import sqlite3
from pathlib import Path

# Define project directories and database file path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "room_finder.db"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.
    
    Features:
    - Automatically creates the parent directory if it does not exist.
    - Enables foreign key constraints (disabled by default in SQLite).
    - Sets row_factory to sqlite3.Row for convenient column access by name.
    """
    # Ensure the directory exists before connecting
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    
    # Enable foreign key constraint enforcement in SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Return rows that can be accessed both by index and by column name
    conn.row_factory = sqlite3.Row
    
    return conn


def init_database(db_path: Path = DEFAULT_DB_PATH) -> None:
    """
    Initializes the database schema by creating required tables if they do not exist:
    1. rooms: Stores unique room records and capacities.
    2. timetable_entries: Stores individual class schedule slots linked to rooms.
    3. source_files: Tracks metadata for timetable files ingested into the system.
    """
    print(f"Connecting to database at: {db_path}")
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. Create 'rooms' table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        room_id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT UNIQUE NOT NULL,
        building TEXT NOT NULL,
        capacity INTEGER
    );
    """)

    # 2. Create 'timetable_entries' table
    # Note: 'room_number' references 'rooms(room_number)' as a foreign key.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS timetable_entries (
        entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT NOT NULL,
        department TEXT,
        semester TEXT,
        section TEXT,
        subject TEXT,
        day TEXT,
        start_time TEXT,
        end_time TEXT,
        source_file TEXT,
        FOREIGN KEY (room_number) REFERENCES rooms(room_number)
            ON UPDATE CASCADE
            ON DELETE CASCADE
    );
    """)

    # 3. Create 'source_files' table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS source_files (
        source_id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT NOT NULL,
        department TEXT,
        semester TEXT
    );
    """)

    conn.commit()
    conn.close()
    print("Database tables initialized successfully.")


if __name__ == "__main__":
    init_database()

