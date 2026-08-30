"""Automatic regional Grid ID assignment for Uganda National Grid.

Grid IDs use the state registry's three-letter grid prefix, for example:
UG-ENT-000401 or UG-KLA-000001.

The next number is derived from existing address records for that prefix, so
legacy IDs are preserved and numbering continues from the highest issued value.
"""
from __future__ import annotations

import re
import threading

from fastapi import HTTPException
from state_geometry import state_for_coordinate

_LOCK = threading.Lock()


def state_assignment_for_coordinate(latitude: float, longitude: float):
    state = state_for_coordinate(latitude, longitude)
    if not state:
        raise HTTPException(status_code=400, detail="Coordinates are outside the validated Uganda state polygons")
    if state.get("ambiguous"):
        raise HTTPException(status_code=409, detail="Coordinates fall exactly on a state boundary and require admin review")
    return state


def next_grid_id(addresses, latitude: float, longitude: float):
    """Return (grid_id, state_metadata), continuing the prefix's sequence."""
    state = state_assignment_for_coordinate(latitude, longitude)
    prefix = state["grid_prefix"].strip().upper()
    pattern = re.compile(rf"^UG-{re.escape(prefix)}-(\d+)$", re.IGNORECASE)

    with _LOCK:
        highest = 0
        existing_ids = set()
        for item in addresses:
            raw = str(item.get("grid_id", "")).strip()
            if not raw:
                continue
            existing_ids.add(raw.upper())
            match = pattern.match(raw)
            if match:
                highest = max(highest, int(match.group(1)))

        candidate = highest + 1
        while True:
            grid_id = f"UG-{prefix}-{candidate:06d}"
            if grid_id.upper() not in existing_ids:
                return grid_id, state
            candidate += 1
