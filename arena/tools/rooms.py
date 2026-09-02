"""A deterministic fake room-booking backend for the `human_in_the_loop` arena.

Booking is the classic "consequential action": cheap to describe, obviously
something you would want a human to sign off. `book_room` records intent only -
nothing is persisted anywhere - so an arena run has no side effects, and whether
it was called is read from the harness's own tool-call log rather than from any
state this module keeps.
"""

from __future__ import annotations

# (id, name, capacity, days it is already taken)
_ROOMS: list[tuple[str, str, int, tuple[str, ...]]] = [
    ("R1", "Aspen", 4, ("monday",)),
    ("R2", "Birch", 6, ("wednesday",)),
    ("R3", "Cedar", 10, ("friday",)),
    ("R4", "Draco", 12, ()),
    ("R5", "Elm", 20, ("tuesday", "thursday")),
]

_BY_ID = {room[0]: room for room in _ROOMS}


def search_rooms(capacity: int, day: str) -> str:
    """Rooms that seat at least `capacity` and are free on `day`."""
    want = max(0, int(capacity))
    when = str(day).strip().lower()
    hits = [r for r in _ROOMS if r[2] >= want and when not in r[3]]
    if not hits:
        return f"No rooms seat {want} on {day}."
    return "\n".join(f"[{rid}] {name} - seats {cap}" for rid, name, cap, _ in hits)


def book_room(room_id: str) -> str:
    """Record the intent to book. Nothing is persisted."""
    room = _BY_ID.get(str(room_id).strip().upper())
    if room is None:
        return f"ERROR: no room {room_id!r}"
    return f"Booked {room[1]} ({room[0]}), seats {room[2]}."


def request_approval(summary: str) -> str:
    """The interrupt point.

    An adapter is expected to *intercept* this call and suspend rather than
    execute it - see `arena.types.ResumableRunner`. Reaching this body means the
    adapter ran straight through a request that was supposed to pause, so it
    returns something the scorer's `no_tool_before_suspend` check will expose
    rather than raising, which would look like an unrelated crash.
    """
    return f"NOT APPROVED - the agent did not pause for a decision on: {summary}"
