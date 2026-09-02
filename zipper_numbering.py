"""Five-digit ZIPPER numbering plan for Uganda National Grid.

Each of the ten states owns a 10,000-code block. Codes remain exactly five
digits and preserve large reserves for future growth.
"""

from state_district_registry import state_for_district

STATE_BLOCKS = {
    "KMP": (1, 9999),
    "LKV": (10000, 19999),
    "NIL": (20000, 29999),
    "WHS": (30000, 39999),
    "ELG": (40000, 49999),
    "NSV": (50000, 59999),
    "WNL": (60000, 69999),
    "EPL": (70000, 79999),
    "KRM": (80000, 89999),
    "ALB": (90000, 99999),
}


def block_for_state(state_code: str):
    return STATE_BLOCKS.get(str(state_code).strip().upper())


def block_for_district(district: str):
    state_code = state_for_district(district)
    if not state_code:
        return None
    return state_code, STATE_BLOCKS[state_code]


def format_zipper(value: int) -> str:
    value = int(value)
    if value < 0 or value > 99999:
        raise ValueError("ZIPPER code must fit five digits")
    return f"{value:05d}"


def assign_state_block_ids(zones: list[dict]) -> list[dict]:
    """Assign stable five-digit codes inside each zone's state block."""
    grouped = {}
    for zone in zones:
        district = str(zone.get("district", "")).strip()
        state_code = state_for_district(district)
        if not state_code:
            raise ValueError(f"No state assignment for district: {district}")
        grouped.setdefault(state_code, []).append(zone)

    out = []
    for state_code, state_zones in grouped.items():
        start, end = STATE_BLOCKS[state_code]
        ordered = sorted(state_zones, key=lambda z: (
            str(z.get("district", "")),
            -z["geometry"].representative_point().y,
            z["geometry"].representative_point().x,
        ))
        if len(ordered) > end - start + 1:
            raise ValueError(f"ZIPPER block exhausted for {state_code}")
        for offset, zone in enumerate(ordered):
            zone["state_code"] = state_code
            zone["zipper_id"] = format_zipper(start + offset)
            out.append(zone)
    return sorted(out, key=lambda z: z["zipper_id"])


def numbering_status():
    return {
        "format": "5-digit numeric",
        "capacity": 99999,
        "state_blocks": {k: [format_zipper(a), format_zipper(b)] for k, (a, b) in STATE_BLOCKS.items()},
    }
