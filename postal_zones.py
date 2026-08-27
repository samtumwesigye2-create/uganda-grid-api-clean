"""Uganda National Grid postal-zone registry.

Postal capacity allocation:
- Kampala Metropolitan: 40 ZIP zones
- other major/dense city regions: 30 ZIP zones each
- remaining state regions: 20 ZIP zones each
- Entebbe + Lake Victoria islands: protected 21xxx region with 10 ZIP zones

Existing Entebbe ZIP codes 21401-21405 remain permanently reserved and are
never renumbered. Codes 21406-21410 extend the same 21xxx postal region to the
Lake Victoria islands.
"""


def _codes(prefix: str, count: int):
    return [f"{prefix}4{i:02d}" for i in range(1, count + 1)]

DENSE_REGIONS = {"JIN", "MBA", "MBL", "GUL"}
STANDARD_REGIONS = {"ARU", "SOR", "MOR", "HOI", "MSK"}

REGIONS = {
    "KLA": {"name": "Kampala Metropolitan", "prefix": "20", "zip_codes": _codes("20", 40), "allocation": "metropolitan"},
    "JIN": {"name": "Nile", "prefix": "22", "zip_codes": _codes("22", 30), "allocation": "dense"},
    "MBA": {"name": "Western Highlands", "prefix": "23", "zip_codes": _codes("23", 30), "allocation": "dense"},
    "MBL": {"name": "Elgon", "prefix": "24", "zip_codes": _codes("24", 30), "allocation": "dense"},
    "GUL": {"name": "Northern Savannah", "prefix": "25", "zip_codes": _codes("25", 30), "allocation": "dense"},
    "ARU": {"name": "West Nile", "prefix": "26", "zip_codes": _codes("26", 20), "allocation": "standard"},
    "SOR": {"name": "Eastern Plains", "prefix": "27", "zip_codes": _codes("27", 20), "allocation": "standard"},
    "MOR": {"name": "Karamoja", "prefix": "28", "zip_codes": _codes("28", 20), "allocation": "standard"},
    "HOI": {"name": "Albertine", "prefix": "29", "zip_codes": _codes("29", 20), "allocation": "standard"},
    "MSK": {"name": "Lake Victoria mainland", "prefix": "30", "zip_codes": _codes("30", 20), "allocation": "standard"},
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
