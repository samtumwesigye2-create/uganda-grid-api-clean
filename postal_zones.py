"""Uganda National Grid postal-zone registry.

Each of the ten initial regions owns one two-digit postal prefix and ten
postal zones. Existing Entebbe ZIP codes 21401-21405 are preserved exactly;
21406-21410 extend coverage outside the protected Entebbe register zones.
ZIP codes identify delivery/service zones; Grid IDs identify properties.
"""


def _ten(prefix):
    return [f"{prefix}4{i:02d}" for i in range(1, 11)]

REGIONS = {
    "KLA": {"name": "Kampala", "prefix": "20", "zip_codes": _ten("20")},
    "ENT": {"name": "Entebbe", "prefix": "21", "zip_codes": _ten("21")},
    "JIN": {"name": "Jinja", "prefix": "22", "zip_codes": _ten("22")},
    "MBA": {"name": "Mbarara", "prefix": "23", "zip_codes": _ten("23")},
    "MBL": {"name": "Mbale", "prefix": "24", "zip_codes": _ten("24")},
    "GUL": {"name": "Gulu", "prefix": "25", "zip_codes": _ten("25")},
    "ARU": {"name": "Arua", "prefix": "26", "zip_codes": _ten("26")},
    "SOR": {"name": "Soroti", "prefix": "27", "zip_codes": _ten("27")},
    "MOR": {"name": "Moroto", "prefix": "28", "zip_codes": _ten("28")},
    "HOI": {"name": "Hoima", "prefix": "29", "zip_codes": _ten("29")},
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
