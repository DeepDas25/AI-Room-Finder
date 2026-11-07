# Timetable Data Validation & Quality Audit Report

**Project**: AI Powered Intelligent Room Availability and Finder System  
**Audit Status**: Complete  
**Validation Date**: November 2026  

---

## 1. Executive Summary

An exhaustive validation audit was conducted on the extracted timetable datasets. The original raw extraction contained **689 entries**, while the verified clean dataset contains **614 high-quality entries** across **36 standardized physical venues**.

- **Zero Database Modifications**: No changes were made to SQLite or the database schema.
- **Original Files Preserved**: All original CSV files remain untouched.
- **Validated CSV Created**: A separate file [`all_timetable_entries_validated.csv`](file:///c:/Users/deepa/OneDrive/Desktop/AI_project/data/processed/all_timetable_entries_validated.csv) was created with clean, verified data.

---

## 2. Audit Findings & Checks

### 2.1 Required Fields & Structural Integrity
| Field | Null / Empty Count | Status |
|---|---|---|
| `department` | 0 | PASS |
| `semester` | 0 | PASS |
| `section` | 0 | PASS |
| `subject` | 0 | PASS |
| `day` | 0 | PASS |
| `start_time` | 0 | PASS |
| `end_time` | 0 | PASS |
| `actual_room` | 0 | PASS |
| `source_file` | 0 | PASS |

### 2.2 Time Format and Chronological Consistency
- **Format**: All start and end times strictly conform to `HH:MM` (24-hour format).
- **Order**: `start_time < end_time` holds true across 100% of rows (zero backwards or zero-duration classes).
- **Duration**: Standard class periods are 50 minutes (e.g. `09:00 - 09:50`, `10:00 - 10:50`). Visiting faculty classes are 60 to 120 minutes.

### 2.3 Room Naming Inconsistencies & Corrections
The audit identified discrepancies where room numbers lost leading zeros during regex extraction:

| Raw Extracted Code | Canonical Standard Code | Physical Building | Reason |
|---|---|---|---|
| `LRC2` | `LRC002` | Learning Resource Centre (LRC) | Restored 3-digit room code matching physical campus signage |
| `LRC7` | `LRC007` | Learning Resource Centre (LRC) | Restored 3-digit room code matching physical campus signage |
| `TB106` | `TB-106` | Technology Block (TB) | Standardized hyphenation for Technology Block |
| `TB105` | `TB-105` | Technology Block (TB) | Standardized hyphenation for Technology Block |
| `Room No. 106` | `IM-106` | Management Block (IM) | Mapped generic 'Room No.' to building code IM |
| `Room No. 102` | `IM-102` | Management Block (IM) | Mapped generic 'Room No.' to building code IM |

### 2.4 Crop Overlap & Duplicate Fragment Audit
The audit detected that in the initial raw extraction of Engineering 1st and 3rd Semesters, cropping bounding boxes across multi-line cells caused:
- **36 truncated fragment entries** (e.g. `'F D'`, `'P D'`, `'D'`, `'C M'`).
- **73 character-interleaved duplicates** (e.g. `'CDar.l cAunluasn...'`, `'DDer.s Digenv...'`).

> [!NOTE]
> These artifacts were completely eliminated in `all_timetable_entries_validated.csv` by reading directly from native PDF table grid cells (`t0[r][c]`), ensuring pristine text integrity.

### 2.5 Multi-Slot Class Duration Preservation
- Multi-hour lab sessions (e.g., Programming Lab from `09:00 to 10:50` or DBMS Lab from `15:00 to 16:50`) are scheduled as **two individual 50-minute entries**.
- **Why this is critical for Room Finder**: A room search executed at `09:15` finds the room occupied, and a search at `10:15` also finds the room occupied. If multi-hour classes were merged into a single non-standard slot, search indexing would suffer point-in-time lookup failures.

### 2.6 Search Engine Readiness & New Columns
To support accurate room availability searches across dates and semesters, the validated CSV introduces four structured columns:
1. `duration_minutes`: Integer duration (50, 60, or 120 minutes).
2. `schedule_type`: Categorizes schedule as `Regular Weekly`, `Date-Dependent Venue`, or `Visiting Faculty Intensive`.
3. `effective_start_date`: ISO 8601 date (`2026-08-03`).
4. `effective_end_date`: ISO 8601 date (`2026-12-15`).

---

## 3. Issues Requiring Human Decisions

The following **4 entries** cannot be resolved automatically without human policy decisions:

| # | Semester | Section | Day | Time | Course / Activity | Current Assigned Room | Issue Requiring Decision |
|---|---|---|---|---|---|---|---|
| 1 | BBA-I | Section C (Fintech) | Monday | 15:00-15:50 | `FA1135 - Introduction to Fintech` | `IET Amphi / IM Amphi` | **Date-dependent venue switch**: In August, class meets in IET Amphitheatre; from September onward, it meets in IM Amphitheatre. Should the database split this into two date-bounded entries? |
| 2 | BBA-I | Section C (Fintech) | Tuesday | 15:00-15:50 | `FA1135 - Introduction to Fintech` | `IET Amphi / IM Amphi` | Same date-dependent venue switch as Monday. |
| 3 | BBA-III | Visiting Faculty | Mon-Fri (Weeks 10-14 Aug & 7-11 Sep) | 11:00-12:00 | `Visiting Faculty Mr. Anil Bhatia - BBA -III Hons. Open Elective` | `Unspecified / TBD` | **Missing Venue**: The timetable specifies times and intensive weeks, but no classroom. Should this occupy a placeholder room (e.g. `TBD / External`)? |
| 4 | BBA-III | Visiting Faculty | Mon-Fri (Weeks 12-16 Oct & 16-20 Nov) | 15:00-17:00 | `Visiting Faculty Mr. Anil Bhatia - BBA -III Fintech` | `Unspecified / TBD` | **Missing Venue**: 2-hour intensive afternoon session without classroom specified. |

