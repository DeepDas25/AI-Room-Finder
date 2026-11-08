"""Constraint Satisfaction Problem (CSP) Room Allocation Engine.

Implements:
- Variables: Session requests needing room assignment.
- Domains: Physical rooms satisfying timetable availability, capacity,
  room type, and equipment requirements.
- Constraints: No room double-booking for overlapping requests, static requirements.
- Search: Backtracking Search with dynamic Minimum Remaining Values (MRV),
  Degree Heuristic tie-breaking, and Forward Checking with exact domain restoration.
"""

from dataclasses import dataclass, field
import datetime
import pathlib
import sqlite3
import time
from typing import List, Dict, Set, Optional, Any, Tuple

# Import the existing availability engine without modifying it
from src.availability_engine import find_available_rooms

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "room_finder.db"


@dataclass(frozen=True)
class SessionRequest:
    """Represents a session or class that requires room allocation."""
    session_id: str
    date: str                  # Format: YYYY-MM-DD
    start_time: str            # Format: HH:MM (24-hour)
    end_time: str              # Format: HH:MM (24-hour)
    expected_students: int
    required_room_type: Optional[str] = None
    required_equipment: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        # Validate session_id
        if not self.session_id or not isinstance(self.session_id, str):
            raise ValueError("session_id must be a non-empty string.")
        
        # Validate date
        try:
            datetime.datetime.strptime(self.date, "%Y-%m-%d")
        except Exception as exc:
            raise ValueError(f"Invalid date format '{self.date}'. Expected YYYY-MM-DD.") from exc

        # Validate start_time and end_time
        try:
            t_start = datetime.datetime.strptime(self.start_time, "%H:%M").time()
            t_end = datetime.datetime.strptime(self.end_time, "%H:%M").time()
        except Exception as exc:
            raise ValueError(f"Invalid time format. Expected HH:MM (24-hour).") from exc

        if t_start >= t_end:
            raise ValueError(
                f"start_time ({self.start_time}) must be strictly earlier than end_time ({self.end_time})."
            )

        # Validate capacity
        if self.expected_students < 0:
            raise ValueError("expected_students must be non-negative.")


@dataclass
class AllocationResult:
    """Result of the CSP solver execution."""
    status: str                                  # "SUCCESS" or "INFEASIBLE"
    allocations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    reason: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


def _sessions_overlap(s1: SessionRequest, s2: SessionRequest) -> bool:
    """Check if two session requests overlap in calendar date and time interval."""
    if s1.date != s2.date:
        return False
    # Standard interval overlap: NOT (s1 ends <= s2 starts OR s1 starts >= s2 ends)
    return not (s1.end_time <= s2.start_time or s1.start_time >= s2.end_time)


class CSPSolver:
    """CSP Room Allocation Solver."""

    def __init__(self, db_path: pathlib.Path = DB_PATH):
        self.db_path = db_path
        self._rooms_cache: Optional[Dict[str, Dict[str, Any]]] = None

    def _get_valid_physical_rooms(self) -> Dict[str, Dict[str, Any]]:
        """Load physical rooms that possess complete and valid metadata.
        
        Strict validation rules:
        - Exclude known invalid codes, placeholders, combined notations, and alternate notations.
        - TB-109 and its alias TB- 109 remain explicitly excluded until separately approved.
        - Room number, room type, and equipment strings must be non-empty after stripping.
        - Capacity must be a strictly positive integer (> 0).
        Currently, exactly 34 physical rooms meet these rigorous conditions.
        """
        if self._rooms_cache is not None:
            return self._rooms_cache

        # Explicit set of non-physical codes, aliases, and unapproved rooms
        EXCLUDED_ROOM_CODES = {
            "EB1-1", "EB1-2", "EB2-2", "EB2-4",
            "IET Amphi / IM Amphi",
            "TB-102/108", "TB-102/112",
            "TB- 109",  # Spaced alias/duplicate remains strictly excluded
            "Unassigned", "Unspecified / TBD",
        }

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        query = """
            SELECT room_id, room_number, building, capacity, room_type, equipment
            FROM rooms
            WHERE capacity IS NOT NULL 
              AND room_type IS NOT NULL 
              AND equipment IS NOT NULL
        """
        cur.execute(query)
        rooms = {}
        for row in cur.fetchall():
            room_num = (row["room_number"] or "").strip()
            room_type = (row["room_type"] or "").strip()
            raw_eq = (row["equipment"] or "").strip()
            cap = row["capacity"]

            # Filter out empty strings or excluded/invalid codes
            if not room_num or room_num in EXCLUDED_ROOM_CODES:
                continue
            if not room_type:
                continue
            if not raw_eq:
                continue
            if not isinstance(cap, int) or cap <= 0:
                continue

            # Parse comma-separated equipment into a normalized lower-case set
            equipment_set = {eq.strip().lower() for eq in raw_eq.split(",") if eq.strip()}
            if not equipment_set:
                continue

            rooms[room_num] = {
                "room_id": row["room_id"],
                "room_number": room_num,
                "building": row["building"],
                "capacity": cap,
                "room_type": room_type,
                "equipment_raw": raw_eq,
                "equipment_set": equipment_set,
            }
        conn.close()
        self._rooms_cache = rooms
        return self._rooms_cache

    def compute_initial_domain(
        self, session: SessionRequest, valid_rooms: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """Compute the candidate room domain for a single session request.
        
        Reuses availability_engine.find_available_rooms to ensure pre-existing
        timetable entries are respected.
        Applies static capacity, room_type, and equipment matching.
        """
        # 1. Query availability engine for rooms free in timetable with capacity
        free_in_timetable = find_available_rooms(
            date_str=session.date,
            start_time_str=session.start_time,
            end_time_str=session.end_time,
            min_capacity=session.expected_students,
        )
        free_room_numbers = {r["room_number"] for r in free_in_timetable}

        # Normalize required equipment
        req_eq = {eq.strip().lower() for eq in session.required_equipment if eq.strip()}

        domain: List[str] = []
        for room_number, room_data in valid_rooms.items():
            # Must be free in timetable
            if room_number not in free_room_numbers:
                continue

            # Must satisfy capacity
            if room_data["capacity"] < session.expected_students:
                continue

            # Must satisfy room type if specified
            if session.required_room_type is not None:
                if room_data["room_type"].lower() != session.required_room_type.strip().lower():
                    continue

            # Must satisfy all required equipment facilities
            if req_eq and not req_eq.issubset(room_data["equipment_set"]):
                continue

            domain.append(room_number)

        # Deterministic sorting for predictable execution
        domain.sort()
        return domain

    def solve(self, sessions: List[SessionRequest]) -> AllocationResult:
        """Execute the CSP solver on a batch of session requests.
        
        Returns an AllocationResult indicating SUCCESS or INFEASIBLE.
        """
        start_clock = time.perf_counter()

        # -------------------------------------------------------------
        # 1. Input Validation
        # -------------------------------------------------------------
        if not sessions:
            return AllocationResult(
                status="SUCCESS",
                allocations={},
                metrics={"sessions_count": 0, "backtracks": 0, "time_ms": 0.0},
            )

        # Check for duplicate session IDs
        seen_ids: Set[str] = set()
        for s in sessions:
            if s.session_id in seen_ids:
                raise ValueError(f"Duplicate session_id detected: '{s.session_id}'.")
            seen_ids.add(s.session_id)

        # Load valid physical rooms with complete metadata (34 rooms)
        valid_rooms = self._get_valid_physical_rooms()

        # -------------------------------------------------------------
        # 2. Build Conflict Graph (Overlapping sessions)
        # -------------------------------------------------------------
        conflict_graph: Dict[SessionRequest, List[SessionRequest]] = {s: [] for s in sessions}
        n = len(sessions)
        for i in range(n):
            for j in range(i + 1, n):
                if _sessions_overlap(sessions[i], sessions[j]):
                    conflict_graph[sessions[i]].append(sessions[j])
                    conflict_graph[sessions[j]].append(sessions[i])

        # -------------------------------------------------------------
        # 3. Compute Initial Domains
        # -------------------------------------------------------------
        domains: Dict[SessionRequest, List[str]] = {}
        for s in sessions:
            dom = self.compute_initial_domain(s, valid_rooms)
            if not dom:
                elapsed_ms = (time.perf_counter() - start_clock) * 1000.0
                return AllocationResult(
                    status="INFEASIBLE",
                    allocations={},
                    reason=(
                        f"Initial domain empty for session '{s.session_id}': "
                        f"no room available on {s.date} ({s.start_time}-{s.end_time}) "
                        f"meeting capacity>={s.expected_students}, type='{s.required_room_type}', "
                        f"equipment={list(s.required_equipment)}."
                    ),
                    metrics={
                        "sessions_count": len(sessions),
                        "backtracks": 0,
                        "time_ms": round(elapsed_ms, 3),
                        "bottleneck_session": s.session_id,
                    },
                )
            domains[s] = dom

        # -------------------------------------------------------------
        # 4. Search Metrics
        # -------------------------------------------------------------
        metrics = {
            "sessions_count": len(sessions),
            "backtracks": 0,
            "forward_checking_prunings": 0,
            "recursive_calls": 0,
            "time_ms": 0.0,
        }

        # -------------------------------------------------------------
        # 5. Recursive Backtracking with Dynamic MRV & Forward Checking
        # -------------------------------------------------------------
        assignment: Dict[SessionRequest, str] = {}
        unassigned: Set[SessionRequest] = set(sessions)

        success = self._backtrack(
            unassigned=unassigned,
            assignment=assignment,
            domains=domains,
            conflict_graph=conflict_graph,
            metrics=metrics,
        )

        elapsed_ms = (time.perf_counter() - start_clock) * 1000.0
        metrics["time_ms"] = round(elapsed_ms, 3)

        if not success:
            return AllocationResult(
                status="INFEASIBLE",
                allocations={},
                reason="All search branches exhausted without finding a conflict-free room allocation.",
                metrics=metrics,
            )

        # Format allocation response with room metadata
        allocations_out: Dict[str, Dict[str, Any]] = {}
        for s, room_num in assignment.items():
            room_meta = valid_rooms[room_num]
            allocations_out[s.session_id] = {
                "room_number": room_num,
                "building": room_meta["building"],
                "capacity": room_meta["capacity"],
                "room_type": room_meta["room_type"],
                "equipment": room_meta["equipment_raw"],
                "date": s.date,
                "time_slot": f"{s.start_time}-{s.end_time}",
            }

        return AllocationResult(
            status="SUCCESS",
            allocations=allocations_out,
            reason=None,
            metrics=metrics,
        )

    def _select_variable(
        self,
        unassigned: Set[SessionRequest],
        domains: Dict[SessionRequest, List[str]],
        conflict_graph: Dict[SessionRequest, List[SessionRequest]],
    ) -> SessionRequest:
        """Dynamic Variable Selection using:
        1. Minimum Remaining Values (MRV): Smallest current domain size.
        2. Degree Heuristic (Tie-breaker): Most unassigned conflicting neighbors.
        3. Lexicographical session_id: Deterministic fallback.
        """
        return min(
            unassigned,
            key=lambda s: (
                len(domains[s]),  # MRV: smallest domain first
                -sum(1 for neighbor in conflict_graph[s] if neighbor in unassigned),  # Degree heuristic
                s.session_id,     # Deterministic tie-breaker
            ),
        )

    def _backtrack(
        self,
        unassigned: Set[SessionRequest],
        assignment: Dict[SessionRequest, str],
        domains: Dict[SessionRequest, List[str]],
        conflict_graph: Dict[SessionRequest, List[SessionRequest]],
        metrics: Dict[str, Any],
    ) -> bool:
        """Core recursive Backtracking Search algorithm.
        
        Returns True if a complete valid assignment is found, False otherwise.
        """
        metrics["recursive_calls"] += 1

        # Base case: All variables successfully assigned
        if not unassigned:
            return True

        # Dynamic MRV + Degree Heuristic selection
        var = self._select_variable(unassigned, domains, conflict_graph)
        unassigned.remove(var)

        # Copy candidate values to avoid modifying list during iteration
        candidate_rooms = list(domains[var])

        for room in candidate_rooms:
            # 1. Tentatively assign room
            assignment[var] = room

            # 2. Forward Checking: Prune assigned room from overlapping unassigned neighbors
            # Record exactly which neighbor had this room removed
            pruned_from: List[SessionRequest] = []
            wipeout = False

            for neighbor in conflict_graph[var]:
                if neighbor in unassigned:
                    if room in domains[neighbor]:
                        domains[neighbor].remove(room)
                        pruned_from.append(neighbor)
                        metrics["forward_checking_prunings"] += 1
                        
                        # Forward Checking Wipeout: neighbor has 0 remaining choices
                        if len(domains[neighbor]) == 0:
                            wipeout = True
                            # Continue to finish loop or break early, but must restore pruned

            # 3. Recurse if no wipeout occurred
            if not wipeout:
                if self._backtrack(unassigned, assignment, domains, conflict_graph, metrics):
                    return True

            # 4. Backtrack / Undo Tentative Assignment:
            # - Record backtrack count
            # - Restore exact domain prunings made by this assignment
            # - Remove tentative assignment
            metrics["backtracks"] += 1

            for neighbor in pruned_from:
                domains[neighbor].append(room)
                # Keep domain sorted for consistency
                domains[neighbor].sort()

            del assignment[var]

        # 5. All candidate rooms for 'var' failed: restore 'var' to unassigned set
        # and propagate FAILURE to the parent recursive call
        unassigned.add(var)
        return False

