"""Uganda National Grid postal-zone registry.

Postal capacity allocation:
- Kampala Metropolitan: 40 active ZIP zones
- other major/dense city regions: 30 active ZIP zones each
- remaining state regions: 20 active ZIP zones each
- Entebbe + Lake Victoria islands: protected 21xxx region with 10 ZIP zones
- each state also owns 20 additional reserve ZIP codes for manual/locality
  allocation where field review shows extra capacity is needed.

Existing Entebbe ZIP codes 21401-21405 remain permanently reserved and are
never renumbered. Codes 21406-21410 extend the same 21xxx postal region to the
Lake Victoria islands.
"""


def _codes(prefix: str, count: int):
    return [f"{prefix}4{i:02d}" for i in range(1, count + 1)]


def _reserve(prefix: str, active_count: int, reserve_count: int = 20):
    return [f"{prefix}4{i:02d}" for i in range(active_count + 1, active_count + reserve_count + 1)]

DENSE_REGIONS = {"JIN", "MBA", "MBL", "GUL"}
STANDARD_REGIONS = {"ARU", "SOR", "MOR", "HOI", "MSK"}


def _region(name, prefix, active_count, allocation):
    return {
        "name": name,
        "prefix": prefix,
        "zip_codes": _codes(prefix, active_count),
        "reserve_zip_codes": _reserve(prefix, active_count, 20),
        "allocation": allocation,
    }

REGIONS = {
    "KLA": _region("Kampala Metropolitan", "20", 40, "metropolitan"),
    "JIN": _region("Nile", "22", 30, "dense"),
    "MBA": _region("Western Highlands", "23", 30, "dense"),
    "MBL": _region("Elgon", "24", 30, "dense"),
    "GUL": _region("Northern Savannah", "25", 30, "dense"),
    "ARU": _region("West Nile", "26", 20, "standard"),
    "SOR": _region("Eastern Plains", "27", 20, "standard"),
    "MOR": _region("Karamoja", "28", 20, "standard"),
    "HOI": _region("Albertine", "29", 20, "standard"),
    "MSK": _region("Lake Victoria mainland", "30", 20, "standard"),
    "ENT": {"name": "Entebbe & Lake Victoria Islands", "prefix": "21", "zip_codes": _codes("21", 10), "reserve_zip_codes": [], "allocation": "islands"},
}

ENTEBBE_ZONES = {
    "21401": "Entebbe Central",
    "21402": "Lake Victoria / Entebbe West",
    "21403": "Airport",
    "21404": "Katabi",
    "21405": "Kigungu",
}

ENTEBBE_BOUNDS = {
    "min_lat": 0.001935,
    "max_lat": 0.1500518,
    "min_lon": 32.3999878,
    "max_lon": 32.5500370,
}


def all_zip_codes(include_reserve: bool = False):
    values = []
    for region in REGIONS.values():
        values.extend(region["zip_codes"])
        if include_reserve:
            values.extend(region.get("reserve_zip_codes", []))
    return values


def region_for_zip(zip_code: str, include_reserve: bool = True):
    value = str(zip_code).strip()
    for code, region in REGIONS.items():
        if value in region["zip_codes"] or (include_reserve and value in region.get("reserve_zip_codes", [])):
            return {"code": code, **region}
    return None


def valid_zip(zip_code: str, include_reserve: bool = True) -> bool:
    return region_for_zip(zip_code, include_reserve=include_reserve) is not None


def entebbe_zip_for_coordinates(latitude: float, longitude: float, require_bounds: bool = True):
    """Preserve the existing Entebbe 21401-21405 coordinate assignments."""
    lat = float(latitude); lon = float(longitude)
    if require_bounds:
        b = ENTEBBE_BOUNDS
        if not (b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]):
            return None
    if lon <= 32.445000: return "21402"
    if lon <= 32.460001:
        if lat <= 0.103221: return "21404"
        return "21403"
    if lat <= 0.044999: return "21405"
    if lon <= 32.500006 and lat <= 0.090002: return "21401"
    return "21403"


def entebbe_zone_for_coordinates(latitude: float, longitude: float):
    zip_code = entebbe_zip_for_coordinates(latitude, longitude)
    if not zip_code: return None
    return {"zip_code": zip_code, "name": ENTEBBE_ZONES[zip_code], "region": "ENT"}
