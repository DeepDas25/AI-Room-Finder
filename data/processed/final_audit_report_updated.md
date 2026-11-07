# Final Audit Report – Updated (Approved Dataset)

**Project:** AI Powered Intelligent Room Availability and Finder System
**Scope:** Approved timetable dataset after resolving date‑dependent FinTech venues and excluding unresolved Visiting‑Faculty entries.

---

## 1. Corrections Applied
| Entry ID | Department | Section | Issue | Resolution |
|----------|------------|---------|-------|------------|
| 516 & 549 | Institute of Management (BBA‑I) – Section C (FinTech) | FinTech | Date‑dependent venue (IET Amphitheatre in August, IM Amphitheatre from September) | Split each entry into **two** rows with explicit `actual_room` and effective dates.
| 613 & 614 | Institute of Management (BBA‑III) – Visiting Faculty | Visiting Faculty | Venue not specified (unresolved) | **Removed** from the approved dataset and saved separately in `visiting_faculty_unresolved.csv`.

## 2. Approved Dataset
- **File:** `data/processed/all_timetable_entries_approved.csv`
- **Total rows (excluding header):** **856**
- The dataset now contains explicit venues for the FinTech classes:
  - `IET Amphitheatre` → effective 2026‑08‑03 – 2026‑08‑31
  - `IM Amphitheatre` → effective 2026‑09‑01 – 2026‑12‑15
- All other rows remain unchanged.

## 3. Unresolved Visiting‑Faculty Entries
- **File:** `data/processed/visiting_faculty_unresolved.csv`
- Contains the two rows (IDs 613, 614) awaiting venue clarification before any inclusion in the database.

## 4. Updated Room Inventory
- **File:** `data/processed/unique_rooms_approved.csv`
- **Total distinct rooms/venues:** **45** (previous 44 plus the newly added `IM Amphitheatre`).
- The new entry:
  ```csv
  room_code,building,room_type,is_regular_classroom,is_alternate_venue,total_scheduled_slots,source_files
  IM Amphitheatre,Campus Amphitheatres,Open Amphitheatre / Auditorium,False,True,2,Time_Table_Final IM V.4 from 3-Aug-26.pdf
  ```

## 5. Verification Summary
- **Row count check:** Approved CSV = 856 rows (matches the expected count after splitting FinTech entries and dropping the 2 Visiting‑Faculty rows).
- **Unique room count:** 45 rooms, consistent with the room list after adding `IM Amphitheatre`.
- **Date‑range handling:** Each FinTech entry now has `effective_start_date` / `effective_end_date` fields reflecting the two periods.
- **Integrity:** No original source CSVs were overwritten.

---

## 6. Next Steps (User Decision Needed)
1. Review the **unresolved Visiting‑Faculty** rows in `visiting_faculty_unresolved.csv` and provide the correct venue information (or confirm they should remain excluded).
2. Once the missing venue data is supplied, we can:
   - Append the resolved rows to `all_timetable_entries_approved.csv` (or create a new merged CSV), and
   - Update the room inventory if new rooms appear.
3. After all data is approved, we can proceed to **insert** the dataset into the SQLite database (the tables created in the initial step).

---

*All operations have been performed without altering the original CSVs or touching the SQLite database.*

[Approved Timetable CSV](file:///C:/Users/deepa/OneDrive/Desktop/AI_project/data/processed/all_timetable_entries_approved.csv)
[Unresolved Visiting Faculty CSV](file:///C:/Users/deepa/OneDrive/Desktop/AI_project/data/processed/visiting_faculty_unresolved.csv)
[Approved Room Inventory CSV](file:///C:/Users/deepa/OneDrive/Desktop/AI_project/data/processed/unique_rooms_approved.csv)

