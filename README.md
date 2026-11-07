# AI Powered Intelligent Room Availability and Finder System

## Phase 1: Database Foundation

This phase implements the foundational SQLite database schema and connection utilities using pure Python standard libraries (no external packages required).

---

## Project Structure

```text
AI_project/
├── Time_Table(BBA+BTECH)/     # Source timetable PDF documents
├── data/
│   └── room_finder.db         # SQLite database file (created automatically)
├── src/
│   ├── __init__.py            # Makes 'src' a Python package
│   └── database.py            # DB connection, schema creation, & initialization logic
├── test_db.py                 # Verification test script
├── .gitignore                 # Python & cache ignore rules
└── README.md                  # Project documentation
```

---

## Database Schema

The database consists of three core tables:

### 1. `rooms`
Stores details of all campus rooms.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `room_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique ID |
| `room_number` | TEXT | UNIQUE, NOT NULL | Room code (e.g., "101", "LT-1") |
| `building` | TEXT | NOT NULL | Building name or block |
| `capacity` | INTEGER | NULLABLE | Max seating capacity |

### 2. `timetable_entries`
Stores scheduled classes and slots linked to rooms.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `entry_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique record ID |
| `room_number` | TEXT | NOT NULL, FOREIGN KEY -> `rooms(room_number)` | Assigned room |
| `department` | TEXT | | Academic department |
| `semester` | TEXT | | Semester name/number |
| `section` | TEXT | | Class section |
| `subject` | TEXT | | Subject name or course code |
| `day` | TEXT | | Day of week (e.g., Monday) |
| `start_time` | TEXT | | Class start time |
| `end_time` | TEXT | | Class end time |
| `source_file` | TEXT | | Filename of timetable source |

### 3. `source_files`
Tracks metadata for timetable files ingested into the system.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `source_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique file record ID |
| `file_name` | TEXT | NOT NULL | Name of the source file |
| `department` | TEXT | | Department for this file |
| `semester` | TEXT | | Semester for this file |

---

## How to Run

### 1. Initialize the Database
You can initialize the database directly:
```bash
python src/database.py
```

### 2. Run the Verification Test
Run the test script to verify database creation, foreign key support, and table schemas:
```bash
python test_db.py
```

