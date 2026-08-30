"""UGAMAP population-based geographic ZIP policy.

Planning policy for the next-generation geographic ZIP generator. Existing,
protected, manual and special ZIP assignments remain authoritative until an
explicit migration is performed.
"""

ZIP_POPULATION_MIN = 1000
ZIP_POPULATION_TARGET = 1650
ZIP_POPULATION_MAX = 2500

# UNG planning baseline used for capacity engineering. Source population
# datasets may be retained separately for geographic/distribution analysis.
NATIONAL_PLANNING_POPULATION = 50_000_000
NATIONAL_TARGET_ZIPS = 30_303  # round(50,000,000 / 1,650)

# Five-digit national architecture.
SPECIAL_NATIONAL_RANGE = (0, 9999)       # 00000-09999
GEOGRAPHIC_RANGE = (10000, 99999)        # 10000-99999

STATE_ALLOCATION_MODE = "planning_population_weighted"
ALLOCATION_HIERARCHY = (
    "state",
    "district",
    "sub_county",
    "population_cluster",
)

REQUIRE_CONTIGUOUS_GEOMETRY = True
ALLOW_CROSS_STATE_ZIPS = False
MANUAL_ASSIGNMENT_MODE = "override_only"
PRESERVE_EXISTING_ZIPS = True
PRESERVE_SPECIAL_00XXX = True


def zip_requirement(population: int) -> int:
    """Return target ZIP count at the 1,650-person planning target."""
    if population < 0:
        raise ValueError("population must be non-negative")
    return round(population / ZIP_POPULATION_TARGET)


def policy_summary():
    return {
        "planning_population": NATIONAL_PLANNING_POPULATION,
        "national_target_zips": NATIONAL_TARGET_ZIPS,
        "population_per_zip": {
            "minimum": ZIP_POPULATION_MIN,
            "target": ZIP_POPULATION_TARGET,
            "maximum": ZIP_POPULATION_MAX,
        },
        "format": "5-digit",
        "special_national_range": "00000-09999",
        "geographic_range": "10000-99999",
        "state_allocation": STATE_ALLOCATION_MODE,
        "hierarchy": list(ALLOCATION_HIERARCHY),
        "contiguous": REQUIRE_CONTIGUOUS_GEOMETRY,
        "cross_state_zips": ALLOW_CROSS_STATE_ZIPS,
        "manual_assignment": MANUAL_ASSIGNMENT_MODE,
        "preserve_existing_zips": PRESERVE_EXISTING_ZIPS,
        "preserve_special_00xxx": PRESERVE_SPECIAL_00XXX,
        "status": "50m_planning_baseline_locked",
    }
