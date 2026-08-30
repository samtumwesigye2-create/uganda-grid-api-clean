"""District-level ZIP capacity registry for UGAMAP.

These are capacity reservations, not live ZIP issuance. Existing ZIP codes and
polygons remain authoritative until an explicit migration is performed.
"""

KAMPALA_CENTRAL_BLOCK = (10000, 19999)

KAMPALA_CENTRAL_DISTRICTS = {
    "Kampala": {"population": 1_875_834, "target_zips": 1138, "start": 10000, "end": 11149},
    "Wakiso": {"population": 3_397_565, "target_zips": 2060, "start": 11150, "end": 13249},
    "Mukono": {"population": 932_672, "target_zips": 566, "start": 13250, "end": 13849},
    "Buikwe": {"population": 519_514, "target_zips": 315, "start": 13850, "end": 14199},
    "Kayunga": {"population": 438_731, "target_zips": 266, "start": 14200, "end": 14499},
    "Mpigi": {"population": 306_003, "target_zips": 186, "start": 14500, "end": 14699},
    "Butambala": {"population": 146_664, "target_zips": 89, "start": 14700, "end": 14799},
    "Gomba": {"population": 199_242, "target_zips": 121, "start": 14800, "end": 14949},
    "Mityana": {"population": 406_225, "target_zips": 247, "start": 14950, "end": 15199},
    "Mubende": {"population": 521_966, "target_zips": 317, "start": 15200, "end": 15549},
    "Luwero": {"population": 614_230, "target_zips": 373, "start": 15550, "end": 15949},
    "Nakaseke": {"population": 251_299, "target_zips": 153, "start": 15950, "end": 16149},
    "Nakasongola": {"population": 226_138, "target_zips": 138, "start": 16150, "end": 16299},
    "Kiboga": {"population": 250_000, "target_zips": 152, "start": 16300, "end": 16499, "population_status": "provisional"},
    "Kyankwanzi": {"population": 278_290, "target_zips": 169, "start": 16500, "end": 16699},
    "Buvuma": {"population": 118_976, "target_zips": 73, "start": 16700, "end": 16799},
}

KAMPALA_CENTRAL_GROWTH_RESERVE = (16800, 19999)


def block_capacity(record):
    return record["end"] - record["start"] + 1


def validate_kampala_central_blocks():
    previous_end = KAMPALA_CENTRAL_BLOCK[0] - 1
    for name, record in KAMPALA_CENTRAL_DISTRICTS.items():
        assert record["start"] == previous_end + 1, f"gap/overlap before {name}"
        assert record["end"] <= KAMPALA_CENTRAL_BLOCK[1]
        assert block_capacity(record) >= record["target_zips"], f"insufficient capacity for {name}"
        previous_end = record["end"]
    assert previous_end + 1 == KAMPALA_CENTRAL_GROWTH_RESERVE[0]
    assert KAMPALA_CENTRAL_GROWTH_RESERVE[1] == KAMPALA_CENTRAL_BLOCK[1]
    return True
