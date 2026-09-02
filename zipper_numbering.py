"""Five-digit ZIPPER numbering plan for Uganda National Grid.

00000-09999 is reserved for national special ZIPs. The active geographic
ZIPPER layer uses 10000-99999, divided into ten non-overlapping 9,000-code
state blocks. This keeps every identifier exactly five digits and prevents the
replacement geographic layer from colliding with the special namespace.
"""

from state_district_registry import state_for_district

STATE_BLOCKS = {
    "KMP": (10000, 18999),
    "LKV": (19000, 27999),
    "NIL": (28000, 36999),
    "WHS": (37000, 45999),
    "ELG": (46000, 54999),
    "NSV": (55000, 63999),
    "WNL": (64000, 72999),
    "EPL": (73000, 81999),
    "KRM": (82000, 90999),
    "ALB": (91000, 99999),
}

SPECIAL_BLOCK = (0, 9999)
GEOGRAPHIC_BLOCK = (10000, 99999)


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
    """Assign stable geographic five-digit codes inside each state's block."""
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
        "capacity": 100000,
        "special_block": [format_zipper(SPECIAL_BLOCK[0]), format_zipper(SPECIAL_BLOCK[1])],
        "geographic_block": [format_zipper(GEOGRAPHIC_BLOCK[0]), format_zipper(GEOGRAPHIC_BLOCK[1])],
        "state_block_size": 9000,
        "state_blocks": {k: [format_zipper(a), format_zipper(b)] for k, (a, b) in STATE_BLOCKS.items()},
        "collision_free": True,
    }
