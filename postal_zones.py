"""Uganda National Grid postal-zone registry.

Postal capacity is allocated by settlement density instead of forcing every
state to have the same number of ZIP zones:
- major/dense urban regions: 25 ZIP zones
- less-dense regions: 15 ZIP zones
- Entebbe + Lake Victoria islands: one protected 21xxx region with 10 ZIP zones

Existing Entebbe ZIP codes 21401-21405 remain permanently reserved and are
never renumbered. Codes 21406-21410 extend the same 21xxx postal region to the
Lake Victoria islands.
"""


def _codes(prefix: str, count: int):
    return [f"{prefix}4{i:02d}" for i in range(1, count + 1)]

# Initial density classes for the ten state postal regions. These can be tuned
# later without changing prefixes or previously issued ZIP numbers.
DENSE_REGIONS = {"KLA", "JIN", "MBA", "MBL", "GUL"}
STANDARD_REGIONS = {"ARU", "SOR", "MOR", "HOI", "MSK"}

REGIONS = {
    "KLA": {"name": "Kampala Metropolitan", "prefix": "20", "zip_codes": _codes("20", 25), "allocation": "dense"},
    "JIN": {"name": "Nile", "prefix": "22", "zip_codes": _codes("22", 25), "allocation": "dense"},
    "MBA": {"name": "Western Highlands", "prefix": "23", "zip_codes": _codes("23", 25), "allocation": "dense"},
    "MBL": {"name": "Elgon", "prefix": "24", "zip_codes": _codes("24", 25), "allocation": "dense"},
    "GUL": {"name": "Northern Savannah", "prefix": "25", "zip_codes": _codes("25", 25), "allocation": "dense"},
    "ARU": {"name": "West Nile", "prefix": "26", "zip_codes": _codes("26", 15), "allocation": "standard"},
    "SOR": {"name": "Eastern Plains", "prefix": "27", "zip_codes": _codes("27", 15), "allocation": "standard"},
    "MOR": {"name": "Karamoja", "prefix": "28", "zip_codes": _codes("28", 15), "allocation": "standard"},
    "HOI": {"name": "Albertine", "prefix": "29", "zip_codes": _codes("29", 15), "allocation": "standard"},
    "MSK": {"name": "Lake Victoria mainland", "prefix": "30", "zip_codes": _codes("30", 15), "allocation": "standard"},
    "ENT": {"name": "Entebbe & Lake Victoria Islands", "prefix": "21", "zip_codes": _codes("21", 10), "allocation": "islands"},
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


def all_zip_codes():
    return [z for region in REGIONS.values() for z in region["zip_codes"]]


def region_for_zip(zip_code: str):
    value = str(zip_code).strip()
    for code, region in REGIONS.items():
        if value in region["zip_codes"]:
            return {"code": code, **region}
    return None


def valid_zip(zip_code: str) -> bool:
    return region_for_zip(zip_code) is not None


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
