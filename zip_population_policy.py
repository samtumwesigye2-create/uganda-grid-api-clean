"""UGAMAP population-based geographic ZIP policy.

This module defines the planning rules for the next-generation automatic
geographic ZIP generator. It intentionally does not renumber existing ZIPs.
Existing/protected/manual/special ZIP assignments remain authoritative until
migration is explicitly performed.
"""

ZIP_POPULATION_MIN = 1000
ZIP_POPULATION_TARGET = 1650
ZIP_POPULATION_MAX = 2500

# Five-digit national architecture.
SPECIAL_NATIONAL_RANGE = (0, 9999)       # 00000-09999
GEOGRAPHIC_RANGE = (10000, 99999)        # 10000-99999

# The first allocation layer is the 10-state architecture. Numeric capacity
# will be apportioned by verified state population before automatic issuance.
STATE_ALLOCATION_MODE = "population_weighted"

# Administrative/geographic hierarchy used to construct contiguous zones.
ALLOCATION_HIERARCHY = (
    "state",
    "district",
    "sub_county",
    "population_cluster",
)

# Guardrails for generated zones.
REQUIRE_CONTIGUOUS_GEOMETRY = True
ALLOW_CROSS_STATE_ZIPS = False
MANUAL_ASSIGNMENT_MODE = "override_only"
PRESERVE_EXISTING_ZIPS = True
PRESERVE_SPECIAL_00XXX = True


def policy_summary():
    return {
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
        "status": "policy_locked_population_data_required_for_generation",
    }
