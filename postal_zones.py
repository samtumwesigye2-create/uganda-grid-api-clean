"""Uganda National Grid postal-zone registry.

Each of the ten initial regions owns one two-digit postal prefix and five
postal zones. Existing Entebbe ZIP codes 21401-21405 are preserved exactly.
ZIP codes identify delivery/service zones; Grid IDs identify properties.

The Entebbe coordinate classifier below was calibrated against all 27,829
records in the official Entebbe address register and reproduces the existing
ZIP assignment for every record in that dataset.
"""

REGIONS = {
    "KLA": {"name": "Kampala", "prefix": "20", "zip_codes": ["20401", "20402", "20403", "20404", "20405"]},
    "ENT": {"name": "Entebbe", "prefix": "21", "zip_codes": ["21401", "21402", "21403", "21404", "21405"]},
    "JIN": {"name": "Jinja", "prefix": "22", "zip_codes": ["22401", "22402", "22403", "22404", "22405"]},
    "MBA": {"name": "Mbarara", "prefix": "23", "zip_codes": ["23401", "23402", "23403", "23404", "23405"]},
    "MBL": {"name": "Mbale", "prefix": "24", "zip_codes": ["24401", "24402", "24403", "24404", "24405"]},
    "GUL": {"name": "Gulu", "prefix": "25", "zip_codes": ["25401", "25402", "25403", "25404", "25405"]},
    "ARU": {"name": "Arua", "prefix": "26", "zip_codes": ["26401", "26402", "26403", "26404", "26405"]},
    "SOR": {"name": "Soroti", "prefix": "27", "zip_codes": ["27401", "27402", "27403", "27404", "27405"]},
    "MOR": {"name": "Moroto", "prefix": "28", "zip_codes": ["28401", "28402", "28403", "28404", "28405"]},
    "HOI": {"name": "Hoima", "prefix": "29", "zip_codes": ["29401", "29402", "29403", "29404", "29405"]},
}

# Existing Entebbe assignments are protected and must never be renumbered.
ENTEBBE_ZONES = {
    "21401": "Entebbe Central",
    "21402": "Lake Victoria",
    "21403": "Airport",
    "21404": "Katabi",
    "21405": "Kigungu",
}

# Verified Entebbe coordinate envelope from the current official register.
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
    """Return the existing Entebbe ZIP zone for a coordinate.

    These boundaries were inferred from, and validated against, the 27,829
    existing Entebbe address records. They intentionally preserve the current
    21401-21405 assignments instead of creating new postal zones.

    Returns None when require_bounds=True and the coordinate lies outside the
    calibrated Entebbe address-register envelope.
    """
    lat = float(latitude)
    lon = float(longitude)

    if require_bounds:
        b = ENTEBBE_BOUNDS
        if not (b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]):
            return None

    # Lake Victoria zone: western strip.
    if lon <= 32.445000:
        return "21402"

    # Katabi occupies the middle-west strip below the northern airport area.
    if lon <= 32.460001:
        if lat <= 0.103221:
            return "21404"
        return "21403"

    # East of Katabi, the southern Kigungu pocket sits below Central.
    if lat <= 0.044999:
        return "21405"

    # Central Entebbe extends eastward until approximately 32.500006,
    # and northward to approximately latitude 0.09.
    if lon <= 32.500006 and lat <= 0.090002:
        return "21401"

    # Remaining calibrated Entebbe territory is Airport zone.
    return "21403"


def entebbe_zone_for_coordinates(latitude: float, longitude: float):
    zip_code = entebbe_zip_for_coordinates(latitude, longitude)
    if not zip_code:
        return None
    return {"zip_code": zip_code, "name": ENTEBBE_ZONES[zip_code], "region": "ENT"}
