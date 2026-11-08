"""Comprehensive Unit Test Suite for CSP Room Allocation Module.

Tests cover:
1. Successful single-session allocation with capacity & equipment matching.
2. Reusing the same room for non-overlapping sessions.
3. Assigning distinct rooms to overlapping sessions.
4. Respecting existing timetable bookings (e.g., EB1-101 occupied at 13:00 on Monday).
5. Enforcing capacity limits.
6. Enforcing room type and facility equipment requirements.
7. Infeasible problem detection with meaningful diagnostic reason.
8. Robust input validation (duplicate IDs, invalid dates/times, negative capacity).
9. Forward checking domain wipeout detection.
10. Authentic backtracking search with exact domain restoration.
"""

import unittest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.csp_solver import CSPSolver, SessionRequest, AllocationResult


class TestCSPSolver(unittest.TestCase):

    def setUp(self):
        self.solver = CSPSolver()
        self.vrooms = self.solver._get_valid_physical_rooms()

    def test_valid_physical_rooms_count(self):
        """Only physical rooms with complete metadata (34 rooms) are loaded."""
        self.assertEqual(
            len(self.vrooms), 34,
            "Exactly 34 physical rooms with complete metadata should be loaded."
        )
        # Verify invalid codes and unapproved strings are excluded
        invalid_codes = ["EB1-1", "EB1-2", "EB2-2", "EB2-4", "TB-109", "TB- 109", "Unassigned"]
        for code in invalid_codes:
            self.assertNotIn(code, self.vrooms, f"Room '{code}' must not be in physical rooms.")

    def test_single_session_allocation(self):
        """A single session with valid requirements is successfully allocated."""
        # Computer Lab on Monday 11:00-11:50
        session = SessionRequest(
            session_id="CS101_Lab",
            date="2026-08-10",
            start_time="11:00",
            end_time="11:50",
            expected_students=40,
            required_room_type="Computer Lab",
            required_equipment=("Computers", "Projector"),
        )
        result = self.solver.solve([session])
        self.assertEqual(result.status, "SUCCESS")
        self.assertIn("CS101_Lab", result.allocations)
        allocated = result.allocations["CS101_Lab"]
        self.assertEqual(allocated["room_type"], "Computer Lab")
        self.assertGreaterEqual(allocated["capacity"], 40)
        self.assertIn("computers", allocated["equipment"].lower())
        self.assertIn("projector", allocated["equipment"].lower())

    def test_reuse_same_room_non_overlapping(self):
        """Non-overlapping sessions on the same date can and do reuse the same room."""
        # Two sessions needing a specialized Seminar Room, one at 09:00-09:50, one at 10:00-10:50.
        # Both require 90 capacity and 'Seminar Room'.
        s1 = SessionRequest(
            session_id="Seminar_Morning",
            date="2026-08-10",
            start_time="09:00",
            end_time="09:50",
            expected_students=90,
            required_room_type="Seminar Room",
        )
        s2 = SessionRequest(
            session_id="Seminar_Midday",
            date="2026-08-10",
            start_time="10:00",
            end_time="10:50",
            expected_students=90,
            required_room_type="Seminar Room",
        )
        result = self.solver.solve([s1, s2])
        self.assertEqual(result.status, "SUCCESS")
        r1 = result.allocations["Seminar_Morning"]["room_number"]
        r2 = result.allocations["Seminar_Midday"]["room_number"]
        # Because EB-006 (IET) is free in both slots (first in sorted domain),
        # both sessions should reuse EB-006 (IET)
        self.assertEqual(r1, r2, "Non-overlapping sessions with same requirements should be allowed to reuse the same room.")

    def test_assign_different_rooms_to_overlapping_sessions(self):
        """Overlapping sessions with identical requirements must receive different physical rooms."""
        s1 = SessionRequest(
            session_id="Concurrent_Lab_1",
            date="2026-08-10",
            start_time="11:00",
            end_time="11:50",
            expected_students=50,
            required_room_type="Computer Lab",
        )
        s2 = SessionRequest(
            session_id="Concurrent_Lab_2",
            date="2026-08-10",
            start_time="11:00",
            end_time="11:50",
            expected_students=50,
            required_room_type="Computer Lab",
        )
        result = self.solver.solve([s1, s2])
        self.assertEqual(result.status, "SUCCESS")
        r1 = result.allocations["Concurrent_Lab_1"]["room_number"]
        r2 = result.allocations["Concurrent_Lab_2"]["room_number"]
        self.assertNotEqual(r1, r2, "Overlapping sessions must not be assigned the same physical room.")

    def test_respects_existing_timetable_bookings(self):
        """Rooms occupied in the existing timetable must never be assigned."""
        # On Monday 2026-08-10 at 13:00-13:50, EB1-101 has scheduled classes in timetable_entries
        s = SessionRequest(
            session_id="Class_Mon_1300",
            date="2026-08-10",
            start_time="13:00",
            end_time="13:50",
            expected_students=50,
            required_room_type="Classroom",
        )
        result = self.solver.solve([s])
        self.assertEqual(result.status, "SUCCESS")
        assigned_room = result.allocations["Class_Mon_1300"]["room_number"]
        self.assertNotEqual(
            assigned_room, "EB1-101",
            "EB1-101 is already booked in timetable at Monday 13:00 and must not be allocated."
        )

    def test_capacity_filtering(self):
        """Rooms with capacity smaller than expected_students must not be assigned."""
        # Require 95 students: only 100-seater rooms (EB-006, IET Amphi, IM Amphi) can qualify
        s = SessionRequest(
            session_id="Large_Cohort",
            date="2026-08-10",
            start_time="09:00",
            end_time="09:50",
            expected_students=95,
        )
        result = self.solver.solve([s])
        self.assertEqual(result.status, "SUCCESS")
        cap = result.allocations["Large_Cohort"]["capacity"]
        self.assertGreaterEqual(cap, 95)

    def test_room_type_and_equipment_filtering(self):
        """Sessions requesting specialized equipment (e.g. Computers) must get matching rooms."""
        s = SessionRequest(
            session_id="Practical_Exam",
            date="2026-08-10",
            start_time="11:00",
            end_time="11:50",
            expected_students=40,
            required_equipment=("Computers",),
        )
        result = self.solver.solve([s])
        self.assertEqual(result.status, "SUCCESS")
        assigned_room = result.allocations["Practical_Exam"]["room_number"]
        # Only Computer Labs possess Computers
        self.assertIn(assigned_room, ["BYOD", "LRC002", "LRC007"])

    def test_infeasible_allocation_reporting(self):
        """When requirements exceed available resources, returns INFEASIBLE with clear reason."""
        # 4 overlapping requests for Computer Labs when only 2 are free at Monday 11:00
        s1 = SessionRequest("Lab1", "2026-08-10", "11:00", "11:50", 50, "Computer Lab")
        s2 = SessionRequest("Lab2", "2026-08-10", "11:00", "11:50", 50, "Computer Lab")
        s3 = SessionRequest("Lab3", "2026-08-10", "11:00", "11:50", 50, "Computer Lab")
        s4 = SessionRequest("Lab4", "2026-08-10", "11:00", "11:50", 50, "Computer Lab")
        result = self.solver.solve([s1, s2, s3, s4])
        self.assertEqual(result.status, "INFEASIBLE")
        self.assertIsNotNone(result.reason)
        self.assertEqual(len(result.allocations), 0)
        self.assertGreater(result.metrics["backtracks"], 0)

    def test_input_validation_errors(self):
        """Validates invalid dates, times, duplicate IDs, and negative capacities."""
        # Duplicate session IDs
        s1 = SessionRequest("DUP_ID", "2026-08-10", "09:00", "09:50", 30)
        s2 = SessionRequest("DUP_ID", "2026-08-10", "10:00", "10:50", 30)
        with self.assertRaises(ValueError) as ctx:
            self.solver.solve([s1, s2])
        self.assertIn("Duplicate session_id", str(ctx.exception))

        # Invalid time order (start >= end)
        with self.assertRaises(ValueError):
            SessionRequest("BadTime", "2026-08-10", "10:00", "09:00", 30)

        # Invalid date format
        with self.assertRaises(ValueError):
            SessionRequest("BadDate", "10-08-2026", "09:00", "09:50", 30)

        # Negative capacity
        with self.assertRaises(ValueError):
            SessionRequest("NegCap", "2026-08-10", "09:00", "09:50", -10)

    def test_forward_checking_wipeout_and_backtracking(self):
        """Authentic test of Forward Checking causing a domain wipeout and the solver backtracking.
        
        Scenario on Monday 2026-08-10 at 11:00-11:50:
        There are only 2 free Computer Labs: ['BYOD', 'LRC002'].
        We submit 3 overlapping sessions:
          - S1 (req: 'Computers') -> Domain: ['BYOD', 'LRC002']
          - S2 (req: 'Computers') -> Domain: ['BYOD', 'LRC002']
          - S3 (req: 'Computers') -> Domain: ['BYOD', 'LRC002']
        
        Because 3 overlapping sessions compete for only 2 rooms:
        1. S1 is tentatively assigned 'BYOD'.
        2. Forward checking prunes 'BYOD' from S2 and S3 -> both left with ['LRC002'].
        3. Next, S2 is tentatively assigned 'LRC002'.
        4. Forward checking prunes 'LRC002' from S3 -> S3's domain becomes EMPTY (wipeout!).
        5. Forward checking detects wipeout, rejects branch, and triggers backtrack.
        6. Solver backtracks, restores 'LRC002' to S3, tries next option, and exhaustively backtracks.
        7. Verified by: status is INFEASIBLE, backtracks == 4, forward_checking_prunings == 6.
        """
        s1 = SessionRequest("CompSession1", "2026-08-10", "11:00", "11:50", 50, required_equipment=("Computers",))
        s2 = SessionRequest("CompSession2", "2026-08-10", "11:00", "11:50", 50, required_equipment=("Computers",))
        s3 = SessionRequest("CompSession3", "2026-08-10", "11:00", "11:50", 50, required_equipment=("Computers",))
        
        # Verify initial domains are indeed 2 rooms each
        d1 = self.solver.compute_initial_domain(s1, self.vrooms)
        d2 = self.solver.compute_initial_domain(s2, self.vrooms)
        d3 = self.solver.compute_initial_domain(s3, self.vrooms)
        self.assertEqual(d1, ["BYOD", "LRC002"])
        self.assertEqual(d2, ["BYOD", "LRC002"])
        self.assertEqual(d3, ["BYOD", "LRC002"])

        result = self.solver.solve([s1, s2, s3])
        self.assertEqual(result.status, "INFEASIBLE")
        self.assertEqual(result.metrics["backtracks"], 4)
        self.assertEqual(result.metrics["forward_checking_prunings"], 6)

    def test_conflict_graph_generation(self):
        """Verify that conflict graph accurately links overlapping sessions
        and does NOT connect non-overlapping sessions across time and dates.
        """
        # Session A: Monday 09:00 - 10:30
        sa = SessionRequest("S_A", "2026-08-10", "09:00", "10:30", 30)
        # Session B: Monday 10:00 - 11:30 (overlaps with S_A between 10:00 and 10:30)
        sb = SessionRequest("S_B", "2026-08-10", "10:00", "11:30", 30)
        # Session C: Monday 10:30 - 12:00 (starts exactly when S_A ends -> NO overlap with S_A, overlaps with S_B)
        sc = SessionRequest("S_C", "2026-08-10", "10:30", "12:00", 30)
        # Session D: Tuesday 10:00 - 11:30 (different date -> NO overlap with any Monday session)
        sd = SessionRequest("S_D", "2026-08-11", "10:00", "11:30", 30)

        sessions = [sa, sb, sc, sd]
        
        # Test helper directly matching solver's internal conflict graph construction logic
        from src.csp_solver import _sessions_overlap
        conflict_graph = {s: [] for s in sessions}
        n = len(sessions)
        for i in range(n):
            for j in range(i + 1, n):
                if _sessions_overlap(sessions[i], sessions[j]):
                    conflict_graph[sessions[i]].append(sessions[j])
                    conflict_graph[sessions[j]].append(sessions[i])

        # Verify S_A edges: overlaps only with S_B
        self.assertIn(sb, conflict_graph[sa])
        self.assertNotIn(sc, conflict_graph[sa], "Back-to-back sessions (10:30 end / 10:30 start) must not overlap.")
        self.assertNotIn(sd, conflict_graph[sa], "Different date sessions must not overlap.")

        # Verify S_B edges: overlaps with S_A and S_C
        self.assertIn(sa, conflict_graph[sb])
        self.assertIn(sc, conflict_graph[sb])
        self.assertNotIn(sd, conflict_graph[sb])

        # Verify S_C edges: overlaps only with S_B
        self.assertNotIn(sa, conflict_graph[sc])
        self.assertIn(sb, conflict_graph[sc])
        self.assertNotIn(sd, conflict_graph[sc])

        # Verify S_D edges: isolated (no neighbors)
        self.assertEqual(len(conflict_graph[sd]), 0)

        # Furthermore, verify that non-overlapping S_A and S_C can be solved and share the same room
        res = self.solver.solve([sa, sc])
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(
            res.allocations["S_A"]["room_number"],
            res.allocations["S_C"]["room_number"],
            "Non-overlapping sessions S_A and S_C should be able to reuse the same physical room."
        )

    def test_domain_restoration_during_backtracking(self):
        """Verify that when a branch fails and backtracks, pruned candidate rooms
        are strictly and accurately restored to neighboring domains without state loss,
        leading to a successful alternative allocation.
        
        Setup: 4 sessions with a bipartite-style conflict structure:
        - S1 overlaps with S2 and S3. Domain: ['R1', 'R2']
        - S2 overlaps with S1, S3, S4. Domain: ['R1', 'R2', 'R3']
        - S3 overlaps with S1, S2, S4. Domain: ['R1', 'R2', 'R3']
        - S4 overlaps with S2 and S3 (does NOT overlap with S1). Domain: ['R2', 'R3']
        
        If S1 tentatively chooses R1:
        - S2 and S3 have R1 pruned.
        - Exploring S2 and S3 downstream causes conflicts that force S4's choices to be exhausted.
        - Backtracking must undo S1's assignment to R1, RESTORE R1 to S2 and S3,
          and instead assign S1 to R2!
        - Once S1 is assigned R2, a complete valid assignment is found:
          S1 -> R2, S2 -> R1, S3 -> R3, S4 -> R2 (since S1 and S4 do not overlap, both can take R2!).
        """
        s1 = SessionRequest("S1", "2026-08-10", "11:00", "11:50", 50)
        s2 = SessionRequest("S2", "2026-08-10", "11:00", "11:50", 50)
        s3 = SessionRequest("S3", "2026-08-10", "11:00", "11:50", 50)
        s4 = SessionRequest("S4", "2026-08-10", "11:00", "11:50", 50)
        
        conflict_graph = {
            s1: [s2, s3],
            s2: [s1, s3, s4],
            s3: [s1, s2, s4],
            s4: [s2, s3]
        }
        initial_domains = {
            s1: ["R1", "R2"],
            s2: ["R1", "R2", "R3"],
            s3: ["R1", "R2", "R3"],
            s4: ["R2", "R3"]
        }
        domains = {k: list(v) for k, v in initial_domains.items()}
        unassigned = {s1, s2, s3, s4}
        assignment = {}
        metrics = {"backtracks": 0, "forward_checking_prunings": 0, "recursive_calls": 0}
        
        success = self.solver._backtrack(unassigned, assignment, domains, conflict_graph, metrics)
        self.assertTrue(success, "Backtracking should successfully recover and find a complete allocation.")
        
        # Verify that multiple backtracks took place to escape dead-ends
        self.assertGreater(metrics["backtracks"], 0)
        
        # Verify valid non-conflicting assignments
        self.assertEqual(assignment[s1], "R2")
        self.assertEqual(assignment[s2], "R1")
        self.assertEqual(assignment[s3], "R3")
        self.assertEqual(assignment[s4], "R2")  # Non-overlapping with S1, so sharing R2 is valid!
        
        # Verify that all 4 variables have been successfully assigned and unassigned is empty
        self.assertEqual(len(unassigned), 0)
        self.assertEqual(len(assignment), 4)


if __name__ == "__main__":
    unittest.main()
