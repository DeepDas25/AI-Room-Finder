"""Room Recommendation Engine.

Combines room availability, room metadata, campus building mapping, and A* shortest-path
search to recommend suitable available rooms, ranked by walking distance from a user's
preferred campus building.

Workflow::

    query = RecommendationQuery(
        preferred_building="TB",
        date="2026-08-10",
        start_time="09:00",
        end_time="10:00",
        min_capacity=30,
        required_room_type="Classroom",
        required_equipment=("AC", "Smartboard"),
    )
    results = recommend_rooms(query)
    for r in results:
        print(r.room_number, r.walking_distance, r.walking_route)

Physical Venue Alias Protection
--------------------------------
**EB-006 (IET) / IET Amphitheatre alias pair:**
    Both database records represent the same physical venue (IET Amphitheatre in EB1).
    Cross-alias conflict detection is implemented in the recommendation layer via
    ``_PHYSICAL_VENUE_ALIAS_GROUPS``. If either alias is booked in the timetable, the
    entire venue is treated as unavailable and neither alias appears in results. When the
    venue is free, only the canonical name (``IET Amphitheatre``) is returned — the
    secondary alias ``EB-006 (IET)`` is suppressed so the venue appears exactly once.
    Database records and the availability engine are not modified.

Reused Modules
--------------
- ``src.availability_engine.find_available_rooms`` – timetable conflict checking.
- ``src.astar_search.find_shortest_route``          – A* campus walking distance.
- ``src.building_mapper.get_campus_node``           – room → campus graph node.
"""

import datetime
import pathlib
import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, Set

from src.availability_engine import find_available_rooms
from src.astar_search import find_shortest_route
from src.building_mapper import get_campus_node
from src.campus_graph import CAMPUS_BUILDINGS

# ---------------------------------------------------------------------------
# Database path – same convention used across the project
# ---------------------------------------------------------------------------
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "room_finder.db"

# ---------------------------------------------------------------------------
# Valid campus graph nodes accepted as preferred building input
# ---------------------------------------------------------------------------
VALID_CAMPUS_NODES: frozenset = frozenset(CAMPUS_BUILDINGS)  # {'EB1', 'EB2', 'TB', 'IM'}

# ---------------------------------------------------------------------------
# Physical Venue Alias Groups
# Each tuple lists all room_number values that represent the same physical space.
# Element [0] is the canonical display name used in recommendation results.
# ---------------------------------------------------------------------------
_PHYSICAL_VENUE_ALIAS_GROUPS: Tuple[Tuple[str, ...], ...] = (
    ("IET Amphitheatre", "EB-006 (IET)"),  # canonical first
)

# Maps every alias -> its canonical room_number
_ALIAS_TO_CANONICAL: Dict[str, str] = {
    alias: group[0]
    for group in _PHYSICAL_VENUE_ALIAS_GROUPS
    for alias in group
}

# Maps every alias -> frozenset of all sibling aliases (including itself)
_ALIAS_TO_GROUP: Dict[str, frozenset] = {
    alias: frozenset(group)
    for group in _PHYSICAL_VENUE_ALIAS_GROUPS
    for alias in group
}

# ---------------------------------------------------------------------------
# Rooms that must never enter recommendation results regardless of metadata.
# This mirrors the strict exclusion list maintained in csp_solver.py and the
# database audit. Keep in sync when new invalid/alias codes are discovered.
# ---------------------------------------------------------------------------
_EXCLUDED_ROOM_CODES: frozenset = frozenset({
    "EB1-1", "EB1-2", "EB2-2", "EB2-4",
    "IET Amphi / IM Amphi",
    "TB-102/108", "TB-102/112",
    "TB- 109",           # Spaced alias/duplicate – excluded permanently
    "Unassigned", "Unspecified / TBD",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecommendationQuery:
    """Encapsulates all parameters for a room recommendation request.

    Attributes
    ----------
    preferred_building : str
        Campus graph node the user is closest to / starting from.
        Must be one of: 'EB1', 'EB2', 'TB', 'IM'.
    date : str
        Target date in ``YYYY-MM-DD`` format.
    start_time : str
        Session start in ``HH:MM`` (24-hour) format.
    end_time : str
        Session end in ``HH:MM`` (24-hour) format.
    min_capacity : int
        Minimum number of seats required. Must be non-negative.
    required_room_type : Optional[str]
        Required room type (e.g. 'Classroom', 'Seminar Room', 'Computer Lab').
        Case-insensitive. ``None`` means no room-type restriction.
    required_equipment : Tuple[str, ...]
        Each item must be present in the room's equipment list.
        Case-insensitive item-by-item comparison. Empty tuple means no restriction.
    """
    preferred_building: str
    date: str
    start_time: str
    end_time: str
    min_capacity: int = 0
    required_room_type: Optional[str] = None
    required_equipment: Tuple[str, ...] = field(default_factory=tuple)


@dataclass
class RecommendedRoom:
    """A single room recommendation result.

    Attributes
    ----------
    room_number : str
        Canonical room identifier (e.g. 'EB2-104', 'TB-109').
    building : str
        Raw database building name (preserved; never modified).
    campus_node : Optional[str]
        Campus graph node ('EB1', 'EB2', 'TB', 'IM') or ``None`` if unmapped.
    capacity : int
        Room seating capacity.
    room_type : str
        Room type classification (e.g. 'Classroom').
    equipment : str
        Raw comma-separated equipment string as stored in the database.
    walking_distance : Optional[float]
        A* shortest walking distance in metres from ``preferred_building``,
        or ``None`` for unmapped rooms.
    walking_route : Optional[List[str]]
        Ordered list of campus nodes from start to this room's building,
        or ``None`` for unmapped rooms.
    """
    room_number: str
    building: str
    campus_node: Optional[str]
    capacity: int
    room_type: str
    equipment: str
    walking_distance: Optional[float]
    walking_route: Optional[List[str]]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_query(query: RecommendationQuery) -> None:
    """Raise ``ValueError`` for any malformed query field.

    Validates:
    - ``preferred_building`` is a known campus graph node.
    - ``date`` follows ``YYYY-MM-DD``.
    - ``start_time`` and ``end_time`` follow ``HH:MM`` (24-hour).
    - ``start_time`` is strictly earlier than ``end_time``.
    - ``min_capacity`` is non-negative.
    """
    if query.preferred_building not in VALID_CAMPUS_NODES:
        raise ValueError(
            f"Invalid preferred_building '{query.preferred_building}'. "
            f"Must be one of: {sorted(VALID_CAMPUS_NODES)}."
        )

    try:
        datetime.datetime.strptime(query.date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"Invalid date format '{query.date}'. Expected YYYY-MM-DD."
        ) from exc

    try:
        t_start = datetime.datetime.strptime(query.start_time, "%H:%M").time()
    except ValueError as exc:
        raise ValueError(
            f"Invalid start_time format '{query.start_time}'. Expected HH:MM (24-hour)."
        ) from exc

    try:
        t_end = datetime.datetime.strptime(query.end_time, "%H:%M").time()
    except ValueError as exc:
        raise ValueError(
            f"Invalid end_time format '{query.end_time}'. Expected HH:MM (24-hour)."
        ) from exc

    if t_start >= t_end:
        raise ValueError(
            f"start_time ({query.start_time}) must be strictly earlier than "
            f"end_time ({query.end_time})."
        )

    if query.min_capacity < 0:
        raise ValueError(
            f"min_capacity cannot be negative (got {query.min_capacity})."
        )


def _load_room_metadata(db_path: pathlib.Path = DB_PATH) -> Dict[str, Dict[str, Any]]:
    """Load complete, valid room metadata records from the database.

    Returns a mapping of room_number → metadata dict for all rooms that satisfy:
    - Non-empty room_number after stripping.
    - Room number not in the exclusion blacklist.
    - Non-empty room_type after stripping.
    - Non-empty equipment string after stripping.
    - Positive integer capacity (> 0).

    Invalid aliases, placeholders, and rooms with missing metadata are silently
    excluded; they must never appear in recommendation results.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT room_id, room_number, building, capacity, room_type, equipment
        FROM rooms
        WHERE capacity IS NOT NULL
          AND room_type IS NOT NULL
          AND equipment IS NOT NULL
    """)
    metadata: Dict[str, Dict[str, Any]] = {}
    for row in cur.fetchall():
        room_num = (row["room_number"] or "").strip()
        room_type = (row["room_type"] or "").strip()
        raw_eq = (row["equipment"] or "").strip()
        cap = row["capacity"]

        if not room_num or room_num in _EXCLUDED_ROOM_CODES:
            continue
        if not room_type:
            continue
        if not raw_eq:
            continue
        if not isinstance(cap, int) or cap <= 0:
            continue

        equipment_items = {eq.strip().lower() for eq in raw_eq.split(",") if eq.strip()}
        if not equipment_items:
            continue

        metadata[room_num] = {
            "room_number": room_num,
            "building": row["building"],
            "capacity": cap,
            "room_type": room_type,
            "equipment_raw": raw_eq,
            "equipment_items": equipment_items,  # normalised lower-case set
        }

    conn.close()
    return metadata


def _meets_requirements(
    room_meta: Dict[str, Any],
    min_capacity: int,
    required_room_type: Optional[str],
    required_equipment: Tuple[str, ...],
) -> bool:
    """Return True if the room meets all static requirements.

    - Capacity: room capacity must be >= min_capacity.
    - Room type: if specified, must match (case-insensitive).
    - Equipment: each requested item must appear as an individual equipment
      entry (case-insensitive item match, not substring).
    """
    if room_meta["capacity"] < min_capacity:
        return False

    if required_room_type is not None:
        if room_meta["room_type"].lower() != required_room_type.strip().lower():
            return False

    for item in required_equipment:
        if item.strip().lower() not in room_meta["equipment_items"]:
            return False

    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def recommend_rooms(
    query: RecommendationQuery,
    include_unmapped_buildings: bool = False,
    db_path: pathlib.Path = DB_PATH,
) -> List[RecommendedRoom]:
    """Find and rank available rooms for a given recommendation query.

    Steps
    -----
    A. Validate query parameters (raises ``ValueError`` on bad input).
    B. Call ``find_available_rooms()`` to get rooms free in the timetable.
    C. Enrich with metadata from the database; discard invalid/incomplete rooms.
    D. Filter by min_capacity, required_room_type, and required_equipment.
    E. Map each candidate to a campus graph node via ``get_campus_node()``.
    F. For mapped rooms, compute walking distance/route via ``find_shortest_route()``.
       For unmapped rooms: skip A* (never invent distances); include or exclude
       them based on ``include_unmapped_buildings``.
    G. Sort results deterministically:
       1. Mapped rooms before unmapped.
       2. Walking distance ascending (mapped only).
       3. Capacity ascending.
       4. Room number ascending.

    Parameters
    ----------
    query : RecommendationQuery
        All search parameters (building, date, time, capacity, type, equipment).
    include_unmapped_buildings : bool, optional
        When ``True``, unmapped rooms (campus_node=None) are appended after
        all mapped rooms. Their walking_distance and walking_route remain None.
        Default: ``False`` (unmapped rooms are excluded).
    db_path : pathlib.Path, optional
        Path to the SQLite database. Defaults to the project-standard DB_PATH.

    Returns
    -------
    List[RecommendedRoom]
        Ranked list of RecommendedRoom objects. Empty list if no rooms qualify.

    Raises
    ------
    ValueError
        For any invalid query parameter.

    Notes
    -----
    **Physical Venue Alias Protection:**
        ``EB-006 (IET)`` and ``IET Amphitheatre`` represent the same physical venue.
        Cross-alias conflict detection ensures that if either alias is booked,
        neither is recommended. When free, only the canonical name (``IET Amphitheatre``)
        is returned.
    """
    # Step A: Input validation
    _validate_query(query)

    # Step B: Availability filtering – delegate entirely to the existing engine
    available = find_available_rooms(
        date_str=query.date,
        start_time_str=query.start_time,
        end_time_str=query.end_time,
        min_capacity=0,  # capacity pre-filter done below after metadata enrichment
    )
    raw_available_numbers: Set[str] = {r["room_number"] for r in available}

    # Step B2: Cross-alias conflict detection
    # For every alias group: if ANY member is missing from raw_available_numbers,
    # the physical venue is booked. Remove ALL members from the available set.
    blocked_rooms: Set[str] = set()
    for alias_room in raw_available_numbers:
        if alias_room in _ALIAS_TO_GROUP:
            for sibling in _ALIAS_TO_GROUP[alias_room]:
                if sibling not in raw_available_numbers:
                    blocked_rooms.update(_ALIAS_TO_GROUP[alias_room])
                    break
    available_room_numbers_set = raw_available_numbers - blocked_rooms

    # Step B3: Deduplication to canonical name
    # Of all aliases that remain available, retain only the canonical name.
    # Non-canonical aliases are discarded so the physical venue appears at most once.
    canonical_seen: Set[str] = set()
    deduplicated_rooms: Set[str] = set()
    for room_num in available_room_numbers_set:
        canonical = _ALIAS_TO_CANONICAL.get(room_num, room_num)
        if canonical not in canonical_seen:
            canonical_seen.add(canonical)
            deduplicated_rooms.add(canonical)

    available_room_numbers: frozenset = frozenset(deduplicated_rooms)

    # Step C: Metadata enrichment – load validated room records
    metadata = _load_room_metadata(db_path)

    # Step D: Requirement filtering
    candidates: List[Dict[str, Any]] = []
    for room_num, room_meta in metadata.items():
        if room_num not in available_room_numbers:
            continue
        if not _meets_requirements(
            room_meta,
            query.min_capacity,
            query.required_room_type,
            query.required_equipment,
        ):
            continue
        candidates.append(room_meta)

    # Steps E & F: Building mapping and A* distance computation
    mapped_results: List[RecommendedRoom] = []
    unmapped_results: List[RecommendedRoom] = []

    for room_meta in candidates:
        campus_node = get_campus_node(room_meta["room_number"], room_meta["building"])

        if campus_node is not None:
            # Mapped room: compute A* walking distance
            route_result = find_shortest_route(query.preferred_building, campus_node)
            mapped_results.append(RecommendedRoom(
                room_number=room_meta["room_number"],
                building=room_meta["building"],
                campus_node=campus_node,
                capacity=room_meta["capacity"],
                room_type=room_meta["room_type"],
                equipment=room_meta["equipment_raw"],
                walking_distance=route_result["total_distance"],
                walking_route=route_result["path"],
            ))
        else:
            # Unmapped room: never invent distance or route
            unmapped_results.append(RecommendedRoom(
                room_number=room_meta["room_number"],
                building=room_meta["building"],
                campus_node=None,
                capacity=room_meta["capacity"],
                room_type=room_meta["room_type"],
                equipment=room_meta["equipment_raw"],
                walking_distance=None,
                walking_route=None,
            ))

    # Step G: Deterministic ranking
    # Mapped rooms: ascending (distance, capacity, room_number)
    mapped_results.sort(
        key=lambda r: (r.walking_distance, r.capacity, r.room_number)
    )
    # Unmapped rooms (if included): ascending (capacity, room_number)
    unmapped_results.sort(key=lambda r: (r.capacity, r.room_number))

    if include_unmapped_buildings:
        return mapped_results + unmapped_results
    return mapped_results

