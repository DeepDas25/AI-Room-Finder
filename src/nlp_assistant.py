"""Natural Language Search Assistant.

Parses plain-English room requests, extracts structured parameters,
validates constraints, and invokes the recommendation engine.

Public Functions:
- ``process_natural_language_request(user_input, reference_now=None, include_unmapped_buildings=False)``

Behaviors Supported:
A. General search ("Find an empty room now") -> all buildings, current time to +60m.
B. Specific building ("Find an empty room in EB2") -> filter_building="EB2".
C. Ambiguous building ("Find an empty room in this building") -> NEEDS_CLARIFICATION.
D. Nearby search ("Find an empty room near EB2") -> preferred_building="EB2", all buildings.
E. Detailed search -> room type, capacity, date, times, equipment.
"""

from dataclasses import dataclass, field
import calendar
import datetime
import re
from typing import Optional, List, Dict, Any, Tuple

from src.room_recommender import (
    RecommendationQuery,
    RecommendedRoom,
    recommend_rooms,
    VALID_CAMPUS_NODES,
)


@dataclass
class NLPResponse:
    """Standardized response from the Natural Language Search Assistant."""
    status: str                                       # "SUCCESS", "NEEDS_CLARIFICATION", "ERROR"
    query: Optional[RecommendationQuery] = None
    recommendations: List[RecommendedRoom] = field(default_factory=list)
    clarification_prompt: Optional[str] = None
    options: List[str] = field(default_factory=list)
    parsed_slots: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Regular Expressions and Synonyms
# ---------------------------------------------------------------------------

_AMBIGUOUS_BUILDING_PATTERN = re.compile(
    r"\b(?:in\s+this\s+building|this\s+building|in\s+here|here|my\s+building|current\s+building)\b",
    re.IGNORECASE,
)

_BUILDING_PATTERNS = [
    ("EB1", re.compile(r"\b(?:eb\s*[-]?\s*1|engineering\s+block\s*[-]?\s*1|eb\s+1|iet\s+amphi(?:theatre)?)\b", re.IGNORECASE)),
    ("EB2", re.compile(r"\b(?:eb\s*[-]?\s*2|engineering\s+block\s*[-]?\s*2|eb\s+2|aic|atal\s+incubation\s+centre)\b", re.IGNORECASE)),
    ("TB", re.compile(r"\b(?:tb|tech\s+block|technology\s+block|cs\s+labs?|computer\s+science\s+labs?|byod)\b", re.IGNORECASE)),
    ("IM", re.compile(r"\b(?:im|management\s+block|institute\s+of\s+management|im\s+amphi(?:theatre)?)\b", re.IGNORECASE)),
]

_NEARBY_TRIGGER_PATTERN = re.compile(
    r"\b(?:near|around|close\s+to|nearby|next\s+to|adjacent\s+to)\b",
    re.IGNORECASE,
)

_ROOM_TYPE_PATTERNS = [
    ("Computer Lab", re.compile(r"\b(?:computer\s+labs?|comp\s+labs?|pc\s+labs?|systems?\s+labs?|labs?)\b", re.IGNORECASE)),
    ("Seminar Room", re.compile(r"\b(?:seminar\s+rooms?|seminar\s+halls?|conference\s+rooms?)\b", re.IGNORECASE)),
    ("Classroom", re.compile(r"\b(?:classrooms?|class\s*rooms?|lecture\s+halls?|lecture\s+rooms?|class)\b", re.IGNORECASE)),
]

_EQUIPMENT_PATTERNS = [
    ("Smartboard", re.compile(r"\b(?:smartboard|smart\s*board|interactive\s+board)\b", re.IGNORECASE)),
    ("Projector", re.compile(r"\b(?:projector|screen)\b", re.IGNORECASE)),
    ("Computers", re.compile(r"\b(?:computers?|pcs?|systems?|laptops?)\b", re.IGNORECASE)),
    ("AC", re.compile(r"\b(?:ac|a/c|air\s*condition(?:er|ing)?)\b", re.IGNORECASE)),
    ("Wi-Fi", re.compile(r"\b(?:wi-?fi|wifi|internet|wireless)\b", re.IGNORECASE)),
    ("Power sockets", re.compile(r"\b(?:power\s*sockets?|charging\s*points?|sockets?|power\s*outlets?|outlets?)\b", re.IGNORECASE)),
]

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


# ---------------------------------------------------------------------------
# Slot Extraction Helpers
# ---------------------------------------------------------------------------

def _check_ambiguity(text: str) -> bool:
    """Return True if user asks for 'this building' or 'here' without naming a building."""
    if _AMBIGUOUS_BUILDING_PATTERN.search(text):
        for _, pat in _BUILDING_PATTERNS:
            if pat.search(text):
                return False
        return True
    return False


def _extract_buildings(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract (filter_building, preferred_building) from text."""
    identified: List[Tuple[str, int, int]] = []
    for code, pat in _BUILDING_PATTERNS:
        for m in pat.finditer(text):
            identified.append((code, m.start(), m.end()))

    if not identified:
        return None, None

    identified.sort(key=lambda x: x[1])

    filter_bldg = None
    pref_bldg = None

    for code, start, _ in identified:
        preceding = text[max(0, start - 25):start]
        if _NEARBY_TRIGGER_PATTERN.search(preceding):
            if pref_bldg is None:
                pref_bldg = code
        else:
            if filter_bldg is None:
                filter_bldg = code

    return filter_bldg, pref_bldg


def _extract_capacity(text: str) -> int:
    """Extract minimum capacity required. Default is 0."""
    pat_for = re.search(
        r"\b(?:for|capacity(?:\s+of)?|seats?|holds?|at\s+least|min(?:imum)?)\s*(\d{1,3})\b(?!\s*(?:hours?|hrs?|minutes?|mins?|am|pm|:))",
        text,
        re.IGNORECASE,
    )
    if pat_for:
        return int(pat_for.group(1))

    pat_students = re.search(
        r"\b(\d{1,3})\s*(?:students?|people|seats?|attendees?|persons?)\b",
        text,
        re.IGNORECASE,
    )
    if pat_students:
        return int(pat_students.group(1))

    return 0


def _extract_room_type(text: str) -> Optional[str]:
    """Extract canonical room type or None."""
    for canonical, pat in _ROOM_TYPE_PATTERNS:
        if pat.search(text):
            return canonical
    return None


def _extract_equipment(text: str) -> Tuple[str, ...]:
    """Extract requested equipment items as a tuple of canonical strings."""
    found: List[str] = []
    for canonical, pat in _EQUIPMENT_PATTERNS:
        if pat.search(text):
            found.append(canonical)
    return tuple(found)


def _extract_date(text: str, ref_now: datetime.datetime) -> Tuple[str, str]:
    """Extract target date string (YYYY-MM-DD) and clean reference.

    Raises:
        ValueError: If an explicit date in query is invalid or impossible.
    """
    clean_text = text.lower()

    if re.search(r"\btomorrow\b", clean_text):
        target = ref_now.date() + datetime.timedelta(days=1)
        return target.strftime("%Y-%m-%d"), "tomorrow"

    if re.search(r"\b(?:today|now)\b", clean_text):
        return ref_now.date().strftime("%Y-%m-%d"), "today"

    weekday_pat = re.search(
        r"\b(this|next)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\b",
        clean_text,
    )
    if weekday_pat:
        modifier = (weekday_pat.group(1) or "").strip()
        day_str = weekday_pat.group(2).strip()
        target_weekday = _WEEKDAYS[day_str]
        current_weekday = ref_now.weekday()

        if modifier == "next":
            days_ahead = ((target_weekday - current_weekday) % 7) + 7
        else:
            days_ahead = (target_weekday - current_weekday) % 7
            if days_ahead == 0 and "this" not in modifier and ref_now.hour >= 20:
                days_ahead = 7

        target = ref_now.date() + datetime.timedelta(days=days_ahead)
        return target.strftime("%Y-%m-%d"), weekday_pat.group(0)

    iso_pat = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if iso_pat:
        y, m, d = int(iso_pat.group(1)), int(iso_pat.group(2)), int(iso_pat.group(3))
        try:
            valid_date = datetime.date(y, m, d)
        except ValueError as exc:
            raise ValueError(f"Invalid date '{iso_pat.group(0)}': {exc}")
        return valid_date.strftime("%Y-%m-%d"), iso_pat.group(0)

    dmy_pat = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", text)
    if dmy_pat:
        d, m, y = int(dmy_pat.group(1)), int(dmy_pat.group(2)), int(dmy_pat.group(3))
        try:
            valid_date = datetime.date(y, m, d)
        except ValueError as exc:
            raise ValueError(f"Invalid date '{dmy_pat.group(0)}': {exc}")
        return valid_date.strftime("%Y-%m-%d"), dmy_pat.group(0)

    month_name_pat = re.search(
        r"\b(?:on\s+)?(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)(?:\s*,?\s*(\d{4}))?\b",
        clean_text,
    )
    if month_name_pat and month_name_pat.group(2) in _MONTHS:
        d = int(month_name_pat.group(1))
        m = _MONTHS[month_name_pat.group(2)]
        y = int(month_name_pat.group(3)) if month_name_pat.group(3) else ref_now.year
        try:
            valid_date = datetime.date(y, m, d)
        except ValueError as exc:
            raise ValueError(f"Invalid date '{month_name_pat.group(0)}': {exc}")
        return valid_date.strftime("%Y-%m-%d"), month_name_pat.group(0)

    month_first_pat = re.search(
        r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?\b",
        clean_text,
    )
    if month_first_pat and month_first_pat.group(1) in _MONTHS:
        m = _MONTHS[month_first_pat.group(1)]
        d = int(month_first_pat.group(2))
        y = int(month_first_pat.group(3)) if month_first_pat.group(3) else ref_now.year
        try:
            valid_date = datetime.date(y, m, d)
        except ValueError as exc:
            raise ValueError(f"Invalid date '{month_first_pat.group(0)}': {exc}")
        return valid_date.strftime("%Y-%m-%d"), month_first_pat.group(0)

    return ref_now.date().strftime("%Y-%m-%d"), "today"


def _extract_duration(text: str) -> Tuple[Optional[datetime.timedelta], bool]:
    """Extract explicit duration if specified.

    Returns:
        (timedelta, True) if an explicit duration was found.
        (None, False) if no duration was found.

    Raises:
        ValueError: If duration is negative, zero, or invalid.
    """
    pat = re.search(
        r"\b(?:for|duration(?:\s+of)?)\s+(-?\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\b",
        text,
        re.IGNORECASE,
    )
    if not pat:
        return None, False

    val_str = pat.group(1)
    unit_str = pat.group(2).lower()
    try:
        val = float(val_str)
    except ValueError:
        raise ValueError(f"Invalid duration value '{val_str}'.")

    if val <= 0:
        raise ValueError(f"Duration must be strictly positive, got {val_str} {unit_str}.")

    if "min" in unit_str:
        delta = datetime.timedelta(minutes=int(val))
    else:
        delta = datetime.timedelta(hours=val)

    if delta <= datetime.timedelta(0):
        raise ValueError(f"Duration must be strictly positive, got {val_str} {unit_str}.")

    return delta, True


def _parse_time_token(token: str, default_meridiem: Optional[str] = None) -> Tuple[int, int]:
    """Parse string like '2', '2:30', '2pm', '14:00' into (hour, minute).

    Raises:
        ValueError: If time format, hour, or minute is invalid.
    """
    token = token.strip().lower()
    if not token:
        raise ValueError("Time string cannot be empty.")

    meridiem = None
    if token.endswith("am"):
        meridiem = "am"
        token = token[:-2].strip()
    elif token.endswith("pm"):
        meridiem = "pm"
        token = token[:-2].strip()
    elif default_meridiem:
        meridiem = default_meridiem

    if ":" in token:
        parts = token.split(":")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError(f"Invalid time format '{token}'.")
        raw_h, raw_m = int(parts[0]), int(parts[1])
    else:
        if not token.isdigit():
            raise ValueError(f"Invalid time format '{token}'.")
        raw_h, raw_m = int(token), 0

    if not (0 <= raw_m <= 59):
        raise ValueError(f"Minute must be between 0 and 59, got {raw_m}.")

    if meridiem is not None:
        if not (1 <= raw_h <= 12):
            raise ValueError(
                f"12-hour format hour must be between 1 and 12 with {meridiem.upper()}, got {raw_h}."
            )
        if meridiem == "pm":
            h = 12 if raw_h == 12 else raw_h + 12
        else:  # am
            h = 0 if raw_h == 12 else raw_h
    else:
        if not (0 <= raw_h <= 23):
            raise ValueError(f"Hour must be between 0 and 23, got {raw_h}.")
        if 1 <= raw_h <= 7:
            h = raw_h + 12
        else:
            h = raw_h

    if not (0 <= h <= 23):
        raise ValueError(f"Derived hour out of range (0-23): {h}.")

    return h, raw_m


def _extract_times(text: str, ref_now: datetime.datetime) -> Tuple[str, str]:
    """Extract start_time and end_time (HH:MM).

    Raises:
        ValueError: If time expressions, intervals, or durations are invalid.
    """
    clean = text.lower()

    # 1. Extract and validate duration if present
    duration_delta, explicit_duration = _extract_duration(clean)

    # 2. Check for time range pattern ("from 2 to 3", "2 to 3", "from 15 to 10")
    range_pat = re.search(
        r"(?:from\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|–|-)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b(?!\s*(?:students?|people|seats?|attendees?|persons?))",
        clean,
    )
    if range_pat:
        t1_raw = range_pat.group(1).strip()
        t2_raw = range_pat.group(2).strip()

        t2_has_am = "am" in t2_raw
        t2_has_pm = "pm" in t2_raw
        t1_has_meridiem = "am" in t1_raw or "pm" in t1_raw

        inherited = None
        if not t1_has_meridiem:
            if t2_has_pm:
                t1_num = int(t1_raw.split(":")[0])
                t2_clean = t2_raw.replace("pm", "").strip()
                t2_num = int(t2_clean.split(":")[0])
                if t1_num <= t2_num:
                    inherited = "pm"
            elif t2_has_am:
                inherited = "am"

        h1, m1 = _parse_time_token(t1_raw, default_meridiem=inherited)
        h2, m2 = _parse_time_token(t2_raw)

        if (h1, m1) >= (h2, m2):
            raise ValueError(
                f"start_time ({h1:02d}:{m1:02d}) must be strictly earlier than end_time ({h2:02d}:{m2:02d})."
            )

        return f"{h1:02d}:{m1:02d}", f"{h2:02d}:{m2:02d}"

    # 3. Check for single start time with "at" or explicit time formatting
    single_at = re.search(
        r"\bat\s+(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)\b(?!\s*(?:students?|people|seats?|attendees?|persons?|capacity))",
        clean,
    )
    explicit_time = re.search(
        r"\b(\d{1,2}:\d{2}(?:\s*(?:am|pm))?|\d{1,2}\s*(?:am|pm))\b(?!\s*(?:students?|people|seats?|attendees?|persons?))",
        clean,
    )

    time_token = None
    if single_at:
        time_token = single_at.group(1).strip()
    elif explicit_time:
        time_token = explicit_time.group(1).strip()

    if time_token is not None:
        sh, sm = _parse_time_token(time_token)
        start_dt = ref_now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        delta = duration_delta if explicit_duration else datetime.timedelta(minutes=60)
        end_dt = start_dt + delta

        if explicit_duration and end_dt.date() > start_dt.date():
            raise ValueError("Requested duration extends beyond the end of the day.")

        if end_dt.date() > start_dt.date():
            end_t = "23:59"
        else:
            end_t = end_dt.strftime("%H:%M")

        if start_dt.strftime("%H:%M") >= end_t:
            raise ValueError(
                f"start_time ({start_dt.strftime('%H:%M')}) must be strictly earlier than end_time ({end_t})."
            )

        return start_dt.strftime("%H:%M"), end_t

    # 4. Default / relative ("now" or query without explicit start time)
    start_t = ref_now.strftime("%H:%M")
    delta = duration_delta if explicit_duration else datetime.timedelta(minutes=60)
    end_dt = ref_now + delta

    if explicit_duration and end_dt.date() > ref_now.date():
        raise ValueError("Requested duration extends beyond the end of the day.")

    if end_dt.date() > ref_now.date():
        end_t = "23:59"
    else:
        end_t = end_dt.strftime("%H:%M")

    if start_t >= end_t:
        raise ValueError(f"start_time ({start_t}) must be strictly earlier than end_time ({end_t}).")

    return start_t, end_t


# ---------------------------------------------------------------------------
# Public Assistant Function
# ---------------------------------------------------------------------------

def process_natural_language_request(
    user_input: str,
    reference_now: Optional[datetime.datetime] = None,
    include_unmapped_buildings: bool = False,
) -> NLPResponse:
    """Parse a plain-English room request and return recommendations or clarification.

    Args:
        user_input: Natural language user query.
        reference_now: Optional datetime anchor for testing and relative dates/times.
        include_unmapped_buildings: Whether unmapped buildings should be included.

    Returns:
        NLPResponse with status SUCCESS, NEEDS_CLARIFICATION, or ERROR.
    """
    if not user_input or not user_input.strip():
        return NLPResponse(
            status="ERROR",
            error_message="User query cannot be empty.",
        )

    ref_now = reference_now or datetime.datetime.now()

    if _check_ambiguity(user_input):
        return NLPResponse(
            status="NEEDS_CLARIFICATION",
            clarification_prompt="Which building are you referring to?",
            options=sorted(list(VALID_CAMPUS_NODES)),
        )

    # 1. Date extraction & validation (fail-fast, before time derivation)
    try:
        date_str, _ = _extract_date(user_input, ref_now)
    except ValueError as exc:
        return NLPResponse(
            status="ERROR",
            error_message=str(exc),
        )

    # 2. Time extraction & validation (duration, bounds, ranges)
    try:
        start_time, end_time = _extract_times(user_input, ref_now)
    except ValueError as exc:
        return NLPResponse(
            status="ERROR",
            error_message=str(exc),
        )

    if not start_time or not end_time:
        return NLPResponse(
            status="ERROR",
            error_message="Could not determine valid time interval.",
        )

    filter_bldg, pref_bldg = _extract_buildings(user_input)
    capacity = _extract_capacity(user_input)
    room_type = _extract_room_type(user_input)
    equipment = _extract_equipment(user_input)

    parsed_slots = {
        "preferred_building": pref_bldg,
        "filter_building": filter_bldg,
        "date": date_str,
        "start_time": start_time,
        "end_time": end_time,
        "min_capacity": capacity,
        "required_room_type": room_type,
        "required_equipment": equipment,
    }

    try:
        query = RecommendationQuery(
            preferred_building=pref_bldg,
            filter_building=filter_bldg,
            date=date_str,
            start_time=start_time,
            end_time=end_time,
            min_capacity=capacity,
            required_room_type=room_type,
            required_equipment=equipment,
        )
    except ValueError as exc:
        return NLPResponse(
            status="ERROR",
            parsed_slots=parsed_slots,
            error_message=str(exc),
        )

    try:
        recommendations = recommend_rooms(
            query=query,
            include_unmapped_buildings=include_unmapped_buildings,
        )
    except Exception as exc:
        return NLPResponse(
            status="ERROR",
            query=query,
            parsed_slots=parsed_slots,
            error_message=f"Recommender error: {exc}",
        )

    return NLPResponse(
        status="SUCCESS",
        query=query,
        recommendations=recommendations,
        parsed_slots=parsed_slots,
    )

