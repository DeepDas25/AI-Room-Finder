# Timetable PDF Extraction & Verification Report

Generated for: **AI Powered Intelligent Room Availability and Finder System**
Status: **Phase 2 Data Extraction Complete (Pending Database Verification)**

---

## 1. Extraction Summary

| Source PDF | Department | Semester / Program | Total Extracted Entries |
|---|---|---|---|
| `Time Table 1st Sem.pdf` | Institute of Engineering and Technology | 1st Semester (Sec A-E, F-J) | **344** |
| `Time Table 3rd sem.pdf` | Institute of Engineering and Technology | 3rd Semester (Sec A-F) | **213** |
| `Time_Table_Final IM V.4 from 3-Aug-26.pdf` | Institute of Management | BBA-I, BBA-III, BBA-V, Visiting | **132** |
| **Total** | **All Departments** | **All Semesters** | **689** |

---

## 2. Unique Rooms and Venues Inventory

A total of **37** distinct rooms and physical venues were discovered across all timetables:

| Room / Venue Code | Building / Location | Category | Regular Room? | Alternate Venue? | Total Scheduled Slots |
|---|---|---|---|---|---|
| `AIC-003` | Atal Incubation Centre (AIC) | Seminar / Workshop Room | No | Yes | 3 |
| `AIC-004` | Atal Incubation Centre (AIC) | Seminar / Workshop Room | No | Yes | 3 |
| `EB-006 (IET)` | Engineering Block (EB) | Classroom | No | Yes | 3 |
| `EB1-002` | Engineering Block 1 (EB-1) | Classroom / Lecture Hall | Yes | No | 18 |
| `EB1-101` | Engineering Block 1 (EB-1) | Classroom / Lecture Hall | Yes | No | 32 |
| `EB1-102` | Engineering Block 1 (EB-1) | Classroom / Lecture Hall | Yes | No | 27 |
| `EB1-103` | Engineering Block 1 (EB-1) | Classroom / Lecture Hall | Yes | No | 26 |
| `EB1-104` | Engineering Block 1 (EB-1) | Classroom / Lecture Hall | Yes | No | 25 |
| `EB2-001` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 14 |
| `EB2-004` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 37 |
| `EB2-005` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 12 |
| `EB2-006` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 14 |
| `EB2-101` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 23 |
| `EB2-102` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 25 |
| `EB2-104` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 19 |
| `EB2-105` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 41 |
| `EB2-106` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 34 |
| `EB2-202` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 33 |
| `EB2-204` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 32 |
| `EB2-205` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 39 |
| `EB2-206` | Engineering Block 2 (EB-2) | Classroom / Lecture Hall | Yes | No | 27 |
| `IET Amphi / IM Amphi` | Campus Amphitheatres | Open Amphitheatre / Auditorium | No | Yes | 2 |
| `IET Amphitheatre` | Campus Amphitheatres | Open Amphitheatre / Auditorium | No | Yes | 18 |
| `IM-102` | Management Block (IM) | Management Classroom / Lab | No | Yes | 5 |
| `IM-106` | Management Block (IM) | Management Classroom / Lab | Yes | Yes | 26 |
| `LRC2` | Learning Resource Centre (LRC) | High-Performance Computing Lab | No | Yes | 4 |
| `LRC7` | Learning Resource Centre (LRC) | High-Performance Computing Lab | No | Yes | 13 |
| `TB-102` | Technology Block (TB) | Computer / Hardware Lab | No | Yes | 2 |
| `TB-102/108` | Technology Block (TB) | Computer / Hardware Lab | No | Yes | 14 |
| `TB-102/112` | Technology Block (TB) | Computer / Hardware Lab | No | Yes | 6 |
| `TB-104` | Technology Block (TB) | Classroom | Yes | No | 35 |
| `TB-105` | Technology Block (TB) | Computer / Hardware Lab | No | Yes | 12 |
| `TB-106` | Technology Block (TB) | Computer / Hardware Lab | No | Yes | 24 |
| `TB-107` | Technology Block (TB) | Classroom | Yes | No | 18 |
| `TB-109` | Technology Block (TB) | Classroom | Yes | No | 19 |
| `TB-112` | Technology Block (TB) | Computer / Hardware Lab | No | Yes | 2 |
| `Unspecified / TBD` | Unassigned | Unassigned / External | Yes | No | 2 |

---

## 3. Entries Requiring Manual Verification

Found **4** entries that have date-dependent venues, special scheduling, or unassigned rooms:

| # | Department | Semester | Section | Day | Time | Assigned Venue | Issue / Reason | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Institute of Management | BBA-I | Section C (Fintech) | Monday | 15:00-15:50 | `IET Amphi / IM Amphi` | Date-dependent venue: August in IET Amphitheatre, September onwards in IM Amphitheatre | Dr. Lokanath Mishra Venue Aug : IET Amphi| Sep Onwards: IM Amphi; Date-dependent venue: Aug in IET Amphi, Sep onwards in IM Amphi |
| 2 | Institute of Management | BBA-I | Section C (Fintech) | Tuesday | 15:00-15:50 | `IET Amphi / IM Amphi` | Date-dependent venue: August in IET Amphitheatre, September onwards in IM Amphitheatre | Dr. Lokanath Mishra Venue Aug : IET Amphi| Sep Onwards: IM Amphi; Date-dependent venue: Aug in IET Amphi, Sep onwards in IM Amphi |
| 3 | Institute of Management | BBA-III | Visiting Faculty | Monday - Friday (Intensive Weeks) | 11:00-12:00 | `Unspecified / TBD` | Visiting faculty schedule; room/venue not specified in timetable | Timings: 11:00AM-12:00Noon; Scheduled weeks: Week : 10th Aug – 14th Aug |
| 4 | Institute of Management | BBA-III | Visiting Faculty | Monday - Friday (Intensive Weeks) | 15:00-17:00 | `Unspecified / TBD` | Visiting faculty schedule; room/venue not specified in timetable | Timings: Mon to Fri: 3:00PM-5:00PM; Scheduled weeks: Week: 12th Oct. – 16th Oct. |

---

## 4. Extraction Error & Anomaly Check

- **Corrupt Files**: None. All 3 PDF files parsed successfully via `pdfplumber`.
- **Missing Days or Timings**: None. All extracted entries contain valid days (Monday-Friday) and start/end time slots.
- **Faculty Placeholder vs Room distinction**: Verified that faculty placeholders like `NF1-CSE` and `NF2-MATHS` were correctly identified as faculty placeholders rather than physical room numbers.
- **Parallel Batches & Split Rooms**: Labs with dual rooms (such as `TB-102/108` and `TB-102/112`) and parallel tutorial/lab hours (such as batch A1 in LRC lab while batch A2 is in regular classroom) have both records preserved without data loss.
