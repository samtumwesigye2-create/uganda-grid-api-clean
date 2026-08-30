"""Provisional UGAMAP 10-state geographic ZIP block plan.

Planning-only: this file MUST NOT renumber or reassign existing live ZIPs.
Population basis is the current reconciled working table. Final activation
requires district/sub-county reconciliation and explicit migration approval.

National/special codes 00000-09999 remain protected and are not state ZIPs.
"""

POPULATION_TARGET_PER_ZIP = 1650
OFFICIAL_UBOS_2024_POPULATION = 45_905_417
WORKING_ASSIGNED_POPULATION = 45_600_207
UNRECONCILED_POPULATION = OFFICIAL_UBOS_2024_POPULATION - WORKING_ASSIGNED_POPULATION

STATE_BLOCKS = (
    # id, state, capital, population, planned_zips, start, end, capacity
    (1, "Kampala Central", "Kampala", 10_483_349, 6_354, 10_000, 27_999, 18_000),
    (2, "Victoria Equatorial", "Masaka", 2_163_017, 1_311, 28_000, 32_999, 5_000),
    (3, "Albertine Rift", "Hoima", 2_792_123, 1_692, 33_000, 38_999, 6_000),
    (4, "Rwenzori Virunga", "Fort Portal", 3_378_840, 2_048, 39_000, 45_999, 7_000),
    (5, "Katonga Highland", "Mbarara", 5_388_662, 3_266, 46_000, 55_999, 10_000),
    (6, "Nile Source", "Jinja", 4_372_349, 2_650, 56_000, 63_999, 8_000),
    (7, "Elgon Karamoja", "Mbale", 3_669_059, 2_224, 64_000, 70_999, 7_000),
    (8, "Kyoga Kwania", "Soroti", 4_839_088, 2_933, 71_000, 79_999, 9_000),
    (9, "Aswa Savannah", "Gulu", 4_614_636, 2_797, 80_000, 88_999, 9_000),
    (10, "West Nile", "Arua", 3_899_084, 2_363, 89_000, 95_999, 7_000),
)

NATIONAL_SPECIAL_BLOCK = (0, 9_999)
NATIONAL_FUTURE_RESERVE = (96_000, 99_999)


def state_block_table():
    rows = []
    for state_id, name, capital, population, needed, start, end, capacity in STATE_BLOCKS:
        rows.append({
            "state_id": state_id,
            "state": name,
            "capital": capital,
            "population_2024_working": population,
            "target_zips": needed,
            "range": f"{start:05d}-{end:05d}",
            "capacity": capacity,
            "unused_capacity": capacity - needed,
            "headroom_percent": round((capacity - needed) / capacity * 100, 1),
        })
    return rows


def validate_plan():
    assert NATIONAL_SPECIAL_BLOCK == (0, 9_999)
    assert sum(x[3] for x in STATE_BLOCKS) == WORKING_ASSIGNED_POPULATION
    assert sum(x[4] for x in STATE_BLOCKS) == 27_638
    previous_end = 9_999
    for row in STATE_BLOCKS:
        start, end, capacity = row[5], row[6], row[7]
        assert start == previous_end + 1
        assert end - start + 1 == capacity
        assert row[4] <= capacity
        previous_end = end
    assert previous_end == 95_999
    assert NATIONAL_FUTURE_RESERVE == (96_000, 99_999)
    return True


validate_plan()
