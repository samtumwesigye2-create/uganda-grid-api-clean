"""National district-level ZIP registry for the Uganda National Grid.

This module is the canonical data model for the new 5-digit federal ZIP plan.
Each state owns a 10,000-code block and districts receive contiguous ranges
inside that block. Unassigned codes remain reserved for future growth.
"""

from typing import Dict, List, Optional


STATE_BLOCKS: Dict[str, dict] = {
    "KYOGA_KWANIA": {
        "state_name": "Kyoga Kwania State",
        "state_code": "SOR",
        "start": 80000,
        "end": 89999,
        "assigned": 3900,
        "reserved": 6100,
        "reserved_ranges": [[83900, 89999]],
        "districts": [
            # Teso portion is intentionally represented as a completed aggregate
            # until its already-approved district rows are copied into this registry.
            {
                "district": "Teso portion",
                "start": 80000,
                "end": 82099,
                "codes": 2100,
                "status": "assigned",
                "aggregate": True,
            },
            {
                "district": "Busia",
                "population_2024": 412018,
                "population_scaled_55m": 497047,
                "start": 82100,
                "end": 82399,
                "codes": 300,
                "status": "assigned",
            },
            {
                "district": "Pallisa",
                "population_2024": 330961,
                "population_scaled_55m": 399082,
                "start": 82400,
                "end": 82649,
                "codes": 250,
                "status": "assigned",
            },
            {
                "district": "Tororo",
                "population_2024": 609117,
                "population_scaled_55m": 734693,
                "start": 82650,
                "end": 83099,
                "codes": 450,
                "status": "assigned",
            },
            {
                "district": "Budaka",
                "population_2024": 281106,
                "population_scaled_55m": 339067,
                "start": 83100,
                "end": 83299,
                "codes": 200,
                "status": "assigned",
            },
            {
                "district": "Butaleja",
                "population_2024": 312713,
                "population_scaled_55m": 377167,
                "start": 83300,
                "end": 83549,
                "codes": 250,
                "status": "assigned",
            },
            {
                "district": "Kibuku",
                "population_2024": 259540,
                "population_scaled_55m": 313051,
                "start": 83550,
                "end": 83749,
                "codes": 200,
                "status": "assigned",
            },
            {
                "district": "Butebo",
                "population_2024": 171289,
                "population_scaled_55m": 206616,
                "start": 83750,
                "end": 83899,
                "codes": 150,
                "status": "assigned",
            },
        ],
    }
}


def _normalize_zip(zip_code) -> Optional[int]:
    try:
        value = int(str(zip_code).strip())
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 99999 else None


def lookup_zip(zip_code) -> Optional[dict]:
    """Resolve a ZIP to state, district/allocation, and reserve status."""
    value = _normalize_zip(zip_code)
    if value is None:
        return None

    for key, state in STATE_BLOCKS.items():
        if state["start"] <= value <= state["end"]:
            result = {
                "zip_code": f"{value:05d}",
                "state_key": key,
                "state_code": state["state_code"],
                "state_name": state["state_name"],
                "state_range": f"{state['start']:05d}-{state['end']:05d}",
                "reserved": True,
                "district": None,
            }
            for district in state["districts"]:
                if district["start"] <= value <= district["end"]:
                    result.update(
                        {
                            "reserved": False,
                            "district": district["district"],
                            "district_range": f"{district['start']:05d}-{district['end']:05d}",
                            "allocation_codes": district["codes"],
                            "aggregate": bool(district.get("aggregate", False)),
                        }
                    )
                    break
            return result
    return None


def state_summary(state_key: str) -> Optional[dict]:
    state = STATE_BLOCKS.get(str(state_key).strip().upper())
    if not state:
        return None
    return {
        "state_name": state["state_name"],
        "state_code": state["state_code"],
        "range": f"{state['start']:05d}-{state['end']:05d}",
        "capacity": state["end"] - state["start"] + 1,
        "assigned": state["assigned"],
        "reserved": state["reserved"],
        "assigned_percent": round(state["assigned"] * 100 / (state["end"] - state["start"] + 1), 2),
        "reserved_percent": round(state["reserved"] * 100 / (state["end"] - state["start"] + 1), 2),
        "districts": state["districts"],
        "reserved_ranges": state["reserved_ranges"],
    }


def validate_registry() -> dict:
    errors: List[str] = []
    for key, state in STATE_BLOCKS.items():
        capacity = state["end"] - state["start"] + 1
        if capacity != 10000:
            errors.append(f"{key}: state capacity is {capacity}, expected 10000")

        ranges = []
        assigned = 0
        for district in state["districts"]:
            expected = district["end"] - district["start"] + 1
            if expected != district["codes"]:
                errors.append(f"{key}/{district['district']}: range size mismatch")
            assigned += district["codes"]
            ranges.append((district["start"], district["end"], district["district"]))

        ranges.sort()
        for prev, cur in zip(ranges, ranges[1:]):
            if cur[0] <= prev[1]:
                errors.append(f"{key}: overlap between {prev[2]} and {cur[2]}")

        if assigned != state["assigned"]:
            errors.append(f"{key}: assigned total {assigned} does not match {state['assigned']}")
        if state["assigned"] + state["reserved"] != capacity:
            errors.append(f"{key}: assigned + reserved does not equal state capacity")

    return {"valid": not errors, "errors": errors, "states_loaded": len(STATE_BLOCKS)}
