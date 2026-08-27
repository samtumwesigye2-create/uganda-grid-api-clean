"""Uganda National Grid postal-zone registry.

Each of the ten initial regions owns one two-digit postal prefix and five
postal zones. Existing Entebbe ZIP codes 21401-21405 are preserved exactly.
ZIP codes identify delivery/service zones; Grid IDs identify properties.
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
