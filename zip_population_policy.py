"""UGAMAP active population-balanced ZIPPER policy.

The legacy 1,000-2,500 / 1,650-target geographic ZIP policy is retired.
The active system uses plain five-digit numeric ZIPPER codes with different
population bands for major-city and rural/other districts.
"""

# Active replacement population bands.
URBAN_ZIPPER_MIN = 3000
URBAN_ZIPPER_TARGET = 4500
URBAN_ZIPPER_MAX = 6000

RURAL_ZIPPER_MIN = 2000
RURAL_ZIPPER_TARGET = 3250
RURAL_ZIPPER_MAX = 4500

# Planning baseline used for capacity engineering only.
NATIONAL_PLANNING_POPULATION = 55_000_000

# 00000-09999 remains a separate national special namespace. Geographic
# ZIPPERs therefore use only 10000-99999 and never collide with special codes.
SPECIAL_NATIONAL_RANGE = (0, 9999)
GEOGRAPHIC_RANGE = (10000, 99999)

STATE_ALLOCATION_MODE = "population_balanced_state_blocks"
ALLOCATION_HIERARCHY = (
    "state",
    "district",
    "sub_county",
    "population_cluster",
)

REQUIRE_CONTIGUOUS_GEOMETRY = True
ALLOW_CROSS_STATE_ZIPPERS = False
LEGACY_GEOGRAPHIC_ZIPS_ACTIVE = False
PRESERVE_SPECIAL_00XXX = True

MAJOR_CITY_DISTRICTS = {
    "Kampala", "Wakiso", "Mukono", "Jinja", "Mbarara", "Mbale",
    "Gulu", "Arua", "Masaka", "Soroti", "Hoima", "Lira",
}


def targets_for(district: str) -> dict:
    """Return the active ZIPPER population policy for a district."""
    urban = str(district or "").strip() in MAJOR_CITY_DISTRICTS
    if urban:
        return {
            "density_class": "urban",
            "minimum": URBAN_ZIPPER_MIN,
            "target": URBAN_ZIPPER_TARGET,
            "maximum": URBAN_ZIPPER_MAX,
        }
    return {
        "density_class": "rural",
        "minimum": RURAL_ZIPPER_MIN,
        "target": RURAL_ZIPPER_TARGET,
        "maximum": RURAL_ZIPPER_MAX,
    }


def zipper_requirement(population: int, district: str) -> int:
    """Return the planned ZIPPER count for a population and district class."""
    population = int(population)
    if population < 0:
        raise ValueError("population must be non-negative")
    if population == 0:
        return 0
    target = targets_for(district)["target"]
    return max(1, round(population / target))


def policy_summary():
    return {
        "system": "ZIPPER",
        "status": "active_replacement",
        "legacy_geographic_zips_active": LEGACY_GEOGRAPHIC_ZIPS_ACTIVE,
        "planning_population": NATIONAL_PLANNING_POPULATION,
        "urban_population_per_zipper": {
            "minimum": URBAN_ZIPPER_MIN,
            "target": URBAN_ZIPPER_TARGET,
            "maximum": URBAN_ZIPPER_MAX,
        },
        "rural_population_per_zipper": {
            "minimum": RURAL_ZIPPER_MIN,
            "target": RURAL_ZIPPER_TARGET,
            "maximum": RURAL_ZIPPER_MAX,
        },
        "format": "5-digit numeric",
        "special_national_range": "00000-09999",
        "geographic_range": "10000-99999",
        "state_allocation": STATE_ALLOCATION_MODE,
        "hierarchy": list(ALLOCATION_HIERARCHY),
        "contiguous": REQUIRE_CONTIGUOUS_GEOMETRY,
        "cross_state_zippers": ALLOW_CROSS_STATE_ZIPPERS,
        "preserve_special_00xxx": PRESERVE_SPECIAL_00XXX,
    }
