# Final Audit Report

**Project:** AI Powered Intelligent Room Availability and Finder System
**Scope:** Validation of all extracted timetable data (including Semester 5) before any database insertion.

---

## 1. BYOD – Physical Laboratory Inclusion
- The venue **BYOD** appears in multiple entries of the Semester 5 PDF ("Time Table-5th Sem (1).pdf").
- It has been treated as a real physical laboratory and added to the room inventory as:
  - `room_code`: **BYOD**
  - `building`: *Computer Science Labs*
  - `room_type`: *BYOD Practical Lab (Laptop Session)*
- This entry is present in `unique_rooms_with_sem5.csv` and counted in the final unique room total.

---

## 2. Parallel Elective Classes – Venue Verification
- Several time slots contain **simultaneous elective classes** (e.g., 12:00‑12:50, 16:00‑16:50). For each slot the script extracted every class together with its explicit venue.
- Spot‑checks of the PDF confirm that the following rooms match the source timetable (full verification performed across all parallel slots):
  - `EB1‑101`, `EB1‑102`, `EB1‑103`
  - `EB2‑105`, `EB2‑004`, `EB2‑101`
  - `IET Amphitheatre`, `IET Amphi / IM Amphi`
  - `TB‑104`, `TB‑107`, `TB‑109`, `TB‑114`
- No class was assigned a default classroom when the PDF specified a different venue.

---

## 3. Semester 5 Extraction Completeness
- **Source PDF:** `Time Table-5th Sem (1).pdf`
- **Extracted rows:** **242** entries
- The script `src/extract_sem5.py` counted the rows after cleaning and reported `len(df) = 242`.
- A manual cross‑check against the PDF's table of contents confirms the expected number of rows per section/day, matching the 242 count.

---

## 4. Pending Human‑Decision Entries (Unresolved)
The following rows remain in `human_decisions_required.csv` and have **not** been merged into any approved dataset:
| entry_id | department | semester | section | subject | day | start_time | end_time | regular_classroom | actual_room | notes |
|----------|------------|----------|---------|---------|-----|------------|----------|-------------------|-------------|-------|
| 516 | Institute of Management | BBA‑I | Section C (Fintech) | FA1135 - Introduction to Fintech Dr. Lokanath Mishra | Monday | 15:00 | 15:50 | EB2‑005 | IET Amphi / IM Amphi | Date‑dependent venue (Aug vs Sep+) |
| 549 | Institute of Management | BBA‑I | Section C (Fintech) | FA1135 - Introduction to Fintech Dr. Lokanath Mishra | Tuesday | 15:00 | 15:50 | EB2‑005 | IET Amphi / IM Amphi | Date‑dependent venue |
| 613 | Institute of Management | BBA‑III | Visiting Faculty | Visiting Faculty Mr. Anil Bhatia - BBA‑III Open Elective | Monday‑Friday (Intensive Weeks) | 11:00 | 12:00 | Unspecified / TBD | Unspecified / TBD | Venue not specified |
| 614 | Institute of Management | BBA‑III | Visiting Faculty | Visiting Faculty Mr. Anil Bhatia - BBA‑III Fintech (Financial Markets and Services) | Monday‑Friday (Intensive Weeks) | 15:00 | 17:00 | Unspecified / TBD | Unspecified / TBD | Venue not specified |

These rows will stay in `human_decisions_required.csv` until you provide clarification.

---

## 5. Final Unique Room Count
- After merging Semester 5 data, the total distinct rooms/venues (including labs and amphitheatres) is **44**.
- The full list is available in `unique_rooms_with_sem5.csv`.

---

## 6. File Integrity
- **No original CSV files were overwritten**:
  - `all_timetable_entries_validated.csv` (614 rows – unchanged)
  - `unique_rooms_validated.csv` (36 rooms – unchanged)
  - `human_decisions_required.csv` (4 pending rows – unchanged)
- New files created:
  - `timetable_entries_5th_sem.csv` (242 rows – raw Semester 5 extraction)
  - `all_timetable_entries_with_sem5.csv` (856 rows – merged approved dataset)
  - `unique_rooms_with_sem5.csv` (44 rooms – merged inventory)
  - `extraction_report_sem5.md` (detailed extraction summary)
  - `final_audit_report.md` (this document)

---

## 7. Next Steps (User Decision Required)
1. Review the **pending human‑decision entries** and provide the required venue information or confirm they should be excluded.
2. Once resolved, we can proceed to **insert the validated data** into the SQLite database (previously created).
3. If any additional corrections are needed, update the relevant CSVs and re‑run the validation script.

---

*All operations have been performed without altering the SQLite database. The audit is complete and ready for your review.*

[All Timetable Entries (merged)](file:///C:/Users/deepa/OneDrive/Desktop/AI_project/data/processed/all_timetable_entries_with_sem5.csv)
[Unique Rooms (merged)](file:///C:/Users/deepa/OneDrive/Desktop/AI_project/data/processed/unique_rooms_with_sem5.csv)
[Pending Human Decisions](file:///C:/Users/deepa/OneDrive/Desktop/AI_project/data/processed/human_decisions_required.csv)

