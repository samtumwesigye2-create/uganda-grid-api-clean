"""Coordinate resolver for the finalized UGAMAP national ZIP architecture.

Coordinates can currently be resolved reliably to an official district polygon and
therefore to that district's allocated ZIP range. Individual ZIP polygons inside
those district ranges have not yet been defined, so this module deliberately does
not invent an exact ZIP from latitude/longitude.
"""
from functools import lru_cache
from shapely.geometry import Point

from national_zip_geometry import _district_geometries
from national_zip_registry import STATE_BLOCKS, DATA_GAPS, COUNTY_SUBSPLIT


def _base_name(name: str) -> str:
    value = str(name or "").strip()
    for suffix in (" (district)", " District", " (city)", " City", " (islands)"):
        if value.lower().endswith(suffix.lower()):
            value = value[: -len(suffix)].strip()
    aliases = {"Sembabule": "Ssembabule"}
    return aliases.get(value, value)


@lru_cache(maxsize=1)
def _allocation_index():
    out = {}
    for state_key, state in STATE_BLOCKS.items():
        for district_name, start, end in state["districts"]:
            key = _base_name(district_name).lower()
            out.setdefault(key, []).append({
                "district": district_name,
                "state_key": state_key,
                "state_name": state["state_name"],
                "capital": state["capital"],
                "zip_start": f"{start:05d}",
                "zip_end": f"{end:05d}",
                "zip_range": f"{start:05d}-{end:05d}",
                "codes": end - start + 1,
                "data_gap": district_name in DATA_GAPS,
                "county_subsplit_flag": district_name in COUNTY_SUBSPLIT,
            })
    return out


def district_allocation_for_coordinate(latitude: float, longitude: float):
    point = Point(float(longitude), float(latitude))
    matches = []
    for source_name, _legacy_state_code, geometry in _district_geometries():
        if geometry.covers(point):
            matches.append(source_name)

    if not matches:
        return None
    if len(matches) > 1:
        return {
            "ambiguous": True,
            "source_districts": sorted(matches),
            "detail": "Coordinate lies on overlapping district polygons",
        }

    source_name = matches[0]
    candidates = _allocation_index().get(_base_name(source_name).lower(), [])
    if not candidates:
        return {
            "ambiguous": False,
            "source_district": source_name,
            "assignment_ready": False,
            "detail": "District polygon exists but has no matching finalized ZIP allocation row",
            "candidates": [],
        }

    # City and district allocations may share one source district polygon. Until city
    # boundary polygons are loaded, expose both candidate ranges instead of guessing.
    exact_ready = len(candidates) == 1
    return {
        "ambiguous": False,
        "source_district": source_name,
        "assignment_ready": False,
        "exact_zip_ready": False,
        "district_range_resolved": exact_ready,
        "candidates": candidates,
        "detail": (
            "District ZIP range resolved; individual ZIP-cluster polygons are not yet loaded"
            if exact_ready
            else "Source geometry does not separate city and district allocations; exact range requires city boundary geometry"
        ),
    }
