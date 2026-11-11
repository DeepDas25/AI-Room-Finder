"""Campus Building Mapping Utilities.

Maps campus room numbers and database building names to the 4 primary campus graph nodes:
    - 'EB1' (Engineering Block 1)
    - 'EB2' (Engineering Block 2)
    - 'TB'  (Technology Block)
    - 'IM'  (Management Block)

Rules:
1. Standard prefixes:
   - 'EB1-' -> 'EB1'
   - 'EB2-' -> 'EB2'
   - 'TB-'  -> 'TB'
   - 'IM-'  -> 'IM'
2. Confirmed specialized locations:
   - Any room number starting with 'AIC' maps to 'EB2'.
   - The exact room number 'EB-006' or 'EB-006 (IET)' (and database building 'Engineering Block (EB)')
     maps to 'EB1' (the physical location of the IET Amphitheatre in EB1).
   - 'IET Amphitheatre' maps to 'EB1'.
   - 'IM Amphitheatre' maps to 'IM'.
   - 'BYOD' and database building 'Computer Science Labs' map to 'TB' (Technology Block).
3. Learning Resource Centre (LRC):
   - 'LRC002', 'LRC007', and building 'Learning Resource Centre (LRC)' strictly remain unmapped (None).
   - LRC precedence is enforced over generic computer lab mappings.
4. Unconfirmed / other specialized locations:
   - Not inferred; return None.
"""

from typing import Optional, Dict

# Explicit building name mapping for known standard blocks
DATABASE_BUILDING_TO_CAMPUS_NODE: Dict[str, str] = {
    "Engineering Block 1 (EB-1)": "EB1",
    "Engineering Block 2 (EB-2)": "EB2",
    "Technology Block (TB)": "TB",
    "Management Block (IM)": "IM",
    "Engineering Block (EB)": "EB1",  # Special case: EB-006 location
    "Computer Science Labs": "TB",     # Special case: CS labs located in TB
}


def get_campus_node(room_number: str, building_name: Optional[str] = None) -> Optional[str]:
    """Resolve a room code and/or building string to its campus graph node ('EB1', 'EB2', 'TB', 'IM').

    Args:
        room_number: Room code string (e.g. 'EB1-101', 'AIC-004', 'EB-006 (IET)', 'TB-102', 'BYOD').
        building_name: Optional raw building name from the database.

    Returns:
        Optional[str]: 'EB1', 'EB2', 'TB', or 'IM' if mapped, or None if unmapped.
    """
    clean_room = (room_number or "").strip()
    clean_building = (building_name or "").strip() if building_name else ""

    # Rule 0: Learning Resource Centre (LRC) rooms must strictly remain unmapped (None).
    # LRC precedence takes priority over any generic Computer Lab or building mapping.
    if clean_room in ("LRC002", "LRC007") or clean_room.startswith("LRC") or "Learning Resource Centre" in clean_building:
        return None

    # Rule 1: Special case for EB-006 / IET Amphitheatre in EB1
    if clean_room in ("EB-006", "EB-006 (IET)", "IET Amphitheatre"):
        return "EB1"
    if clean_building == "Engineering Block (EB)":
        return "EB1"

    # Rule 2: Special case for IM Amphitheatre in IM
    if clean_room == "IM Amphitheatre":
        return "IM"

    # Rule 3: Any room starting with 'AIC' maps to 'EB2'
    if clean_room.startswith("AIC"):
        return "EB2"

    # Rule 4: Confirmed Technology Block Computer Labs
    # BYOD and Computer Science Labs are physically located in Technology Block (TB)
    if clean_room == "BYOD":
        return "TB"
    if clean_building == "Computer Science Labs":
        return "TB"

    # Rule 5: Standard room code prefixes
    if clean_room.startswith("EB1-"):
        return "EB1"
    if clean_room.startswith("EB2-"):
        return "EB2"
    if clean_room.startswith("TB-"):
        return "TB"
    if clean_room.startswith("IM-"):
        return "IM"

    # Rule 6: Database building name fallback for standard blocks
    if clean_building in DATABASE_BUILDING_TO_CAMPUS_NODE:
        return DATABASE_BUILDING_TO_CAMPUS_NODE[clean_building]

    # Rule 7: Unmapped / other specialized venues return None (no guessing)
    return None

