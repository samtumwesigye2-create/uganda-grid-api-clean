"""Generate five deterministic ZIP sub-polygons inside each custom state.

This is the geometric framework for nationwide ZIP assignment. Entebbe's
existing 21401-21405 classifier remains authoritative and is NOT replaced.

For each non-Entebbe state, the state polygon is split into five longitude
bands of equal geographic width, clipped to the exact state geometry. The
result therefore covers the state without extending outside its boundary.
This is an initial operational zoning scheme; future reviewed administrative
ZIP polygons can replace these generated zones without changing ZIP numbers.
"""
from functools import lru_cache

from shapely.geometry import box, Point
from shapely.ops import unary_union

from state_geometry import _state_geometries

STATE_TO_POSTAL = {
    "KMP": ("KLA", ["20401", "20402", "20403", "20404", "20405"]),
    "LKV": ("ENT", ["21401", "21402", "21403", "21404", "21405"]),
    "NIL": ("JIN", ["22401", "22402", "22403", "22404", "22405"]),
    "WHS": ("MBA", ["23401", "23402", "23403", "23404", "23405"]),
    "ELG": ("MBL", ["24401", "24402", "24403", "24404", "24405"]),
    "NSV": ("GUL", ["25401", "25402", "25403", "25404", "25405"]),
    "WNL": ("ARU", ["26401", "26402", "26403", "26404", "26405"]),
    "EPL": ("SOR", ["27401", "27402", "27403", "27404", "27405"]),
    "KRM": ("MOR", ["28401", "28402", "28403", "28404", "28405"]),
    "ALB": ("HOI", ["29401", "29402", "29403", "29404", "29405"]),
}


@lru_cache(maxsize=1)
def _zones():
    result = {}
    for props, state_geom in _state_geometries():
        state_code = props["state_code"]
        postal_region, zip_codes = STATE_TO_POSTAL[state_code]
        minx, miny, maxx, maxy = state_geom.bounds
        width = (maxx - minx) / 5.0
        zones = []
        for i, zip_code in enumerate(zip_codes):
            left = minx + i * width
            right = maxx if i == 4 else minx + (i + 1) * width
            band = box(left, miny - 1.0, right, maxy + 1.0)
            geom = state_geom.intersection(band)
            if geom.is_empty or not geom.is_valid:
                raise ValueError(f"Invalid ZIP geometry {zip_code} in {state_code}")
            zones.append((zip_code, geom))

        union = unary_union([g for _, g in zones])
        if state_geom.difference(union).area > 1e-12 or union.difference(state_geom).area > 1e-12:
            raise ValueError(f"ZIP zones do not exactly cover state {state_code}")
        for i, (za, ga) in enumerate(zones):
            for zb, gb in zones[i + 1:]:
                if ga.intersection(gb).area > 1e-12:
                    raise ValueError(f"ZIP overlap {za}/{zb}")
        result[state_code] = {"postal_region": postal_region, "zones": zones}
    return result


def zip_for_coordinate(latitude: float, longitude: float, state_code: str):
    """Resolve a coordinate to exactly one generated ZIP inside its state."""
    state = _zones().get(state_code)
    if not state:
        return None
    point = Point(float(longitude), float(latitude))
    matches = [(z, g) for z, g in state["zones"] if g.covers(point)]
    if not matches:
        return None
    # On a shared internal boundary, choose the lower-numbered ZIP
    # deterministically. The point is still inside only one state.
    zip_code = sorted(z for z, _ in matches)[0]
    return {"zip_code": zip_code, "region": state["postal_region"], "name": ""}


def validation_status():
    zones = _zones()
    return {"state_count": len(zones), "zones_per_state": {k: len(v["zones"]) for k, v in zones.items()}}
