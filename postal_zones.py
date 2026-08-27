"""Uganda National Grid postal-zone registry.

Ten state postal regions each own ten ZIP zones. Entebbe is a protected
city-level enclave inside Kampala Metropolitan and permanently keeps its
existing 21401-21405 ZIP codes; those five codes are not reused anywhere else.
"""


def _ten(prefix):
    return [f"{prefix}4{i:02d}" for i in range(1, 11)]

REGIONS = {
    "KLA": {"name": "Kampala Metropolitan", "prefix": "20", "zip_codes": _ten("20")},
    "JIN": {"name": "Nile", "prefix": "22", "zip_codes": _ten("22")},
    "MBA": {"name": "Western Highlands", "prefix": "23", "zip_codes": _ten("23")},
    "MBL": {"name": "Elgon", "prefix": "24", "zip_codes": _ten("24")},
    "GUL": {"name": "Northern Savannah", "prefix": "25", "zip_codes": _ten("25")},
    "ARU": {"name": "West Nile", "prefix": "26", "zip_codes": _ten("26")},
    "SOR": {"name": "Eastern Plains", "prefix": "27", "zip_codes": _ten("27")},
    "MOR": {"name": "Karamoja", "prefix": "28", "zip_codes": _ten("28")},
    "HOI": {"name": "Albertine", "prefix": "29", "zip_codes": _ten("29")},
    "MSK": {"name": "Lake Victoria", "prefix": "30", "zip_codes": _ten("30")},
    "ENT": {"name": "Entebbe", "prefix": "21", "zip_codes": ["21401", "21402", "21403", "21404", "21405"]},
}

ENTEBBE_ZONES = {
    "21401": "Entebbe Central",
    "21402": "Lake Victoria",
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
