"""District-level ZIP capacity registry for UGAMAP.

These are capacity reservations, not live ZIP issuance. Existing ZIP codes and
polygons remain authoritative until an explicit migration is performed.
"""

KAMPALA_CENTRAL_BLOCK = (10000, 19999)
VICTORIA_EQUATORIAL_BLOCK = (20000, 29999)
ALBERTINE_RIFT_BLOCK = (30000, 39999)
RWENZORI_VIRUNGA_BLOCK = (40000, 49999)

KAMPALA_CENTRAL_DISTRICTS = {
    "Kampala": {"population": 2_262_460, "target_zips": 1371, "start": 10000, "end": 11399},
    "Wakiso": {"population": 4_098_479, "target_zips": 2484, "start": 11400, "end": 13899},
    "Mukono": {"population": 1_124_949, "target_zips": 682, "start": 13900, "end": 14599},
    "Buikwe": {"population": 626_626, "target_zips": 380, "start": 14600, "end": 14999},
    "Kayunga": {"population": 529_151, "target_zips": 321, "start": 15000, "end": 15349},
    "Mpigi": {"population": 369_081, "target_zips": 224, "start": 15350, "end": 15599},
    "Butambala": {"population": 176_906, "target_zips": 107, "start": 15600, "end": 15749},
    "Gomba": {"population": 240_361, "target_zips": 146, "start": 15750, "end": 15899},
    "Mityana": {"population": 490_034, "target_zips": 297, "start": 15900, "end": 16199},
    "Mubende": {"population": 629_584, "target_zips": 382, "start": 16200, "end": 16599},
    "Luwero": {"population": 740_927, "target_zips": 449, "start": 16600, "end": 17049},
    "Nakaseke": {"population": 303_102, "target_zips": 184, "start": 17050, "end": 17249},
    "Nakasongola": {"population": 272_747, "target_zips": 165, "start": 17250, "end": 17449},
    "Kiboga": {"population": 301_533, "target_zips": 183, "start": 17450, "end": 17649},
    "Kyankwanzi": {"population": 335_640, "target_zips": 203, "start": 17650, "end": 17899},
    "Buvuma": {"population": 143_505, "target_zips": 87, "start": 17900, "end": 17999},
}
KAMPALA_CENTRAL_GROWTH_RESERVE = (18000, 19999)

VICTORIA_EQUATORIAL_DISTRICTS = {
    "Masaka District": {"population": 139_033, "target_zips": 84, "start": 20000, "end": 20099},
    "Masaka City": {"population": 217_104, "target_zips": 132, "start": 20100, "end": 20249},
    "Kalungu": {"population": 266_421, "target_zips": 161, "start": 20250, "end": 20449},
    "Bukomansimbi": {"population": 237_679, "target_zips": 144, "start": 20450, "end": 20599},
    "Lwengo": {"population": 391_389, "target_zips": 237, "start": 20600, "end": 20849},
    "Ssembabule": {"population": 368_612, "target_zips": 223, "start": 20850, "end": 21099},
    "Lyantonde": {"population": 160_651, "target_zips": 97, "start": 21100, "end": 21199},
    "Rakai": {"population": 402_389, "target_zips": 244, "start": 21200, "end": 21449},
    "Kyotera": {"population": 341_344, "target_zips": 207, "start": 21450, "end": 21699},
    "Kalangala": {"population": 84_429, "target_zips": 51, "start": 21700, "end": 21799},
}
VICTORIA_EQUATORIAL_GROWTH_RESERVE = (21800, 29999)

ALBERTINE_RIFT_DISTRICTS = {
    "Hoima District": {"population": 308_214, "target_zips": 187, "start": 30000, "end": 30199},
    "Hoima City": {"population": 169_357, "target_zips": 103, "start": 30200, "end": 30349},
    "Kibaale": {"population": 285_555, "target_zips": 173, "start": 30350, "end": 30549},
    "Masindi": {"population": 410_062, "target_zips": 249, "start": 30550, "end": 30799},
    "Buliisa": {"population": 201_160, "target_zips": 122, "start": 30800, "end": 30949},
    "Kiryandongo": {"population": 436_900, "target_zips": 265, "start": 30950, "end": 31249},
    "Kagadi": {"population": 563_146, "target_zips": 341, "start": 31250, "end": 31599},
    "Kakumiro": {"population": 513_713, "target_zips": 311, "start": 31600, "end": 31949},
    "Kikuube": {"population": 455_155, "target_zips": 276, "start": 31950, "end": 32249},
}
ALBERTINE_RIFT_GROWTH_RESERVE = (32250, 39999)

RWENZORI_VIRUNGA_DISTRICTS = {
    "Kabarole": {"population": 275_839, "target_zips": 167, "start": 40000, "end": 40199},
    "Fort Portal City": {"population": 164_689, "target_zips": 100, "start": 40200, "end": 40299},
    "Bunyangabu": {"population": 262_262, "target_zips": 159, "start": 40300, "end": 40499},
    "Kamwenge": {"population": 403_704, "target_zips": 245, "start": 40500, "end": 40749},
    "Kitagwenda": {"population": 221_451, "target_zips": 134, "start": 40750, "end": 40899},
    "Kyegegwa": {"population": 599_981, "target_zips": 364, "start": 40900, "end": 41299},
    "Kyenjojo": {"population": 651_309, "target_zips": 395, "start": 41300, "end": 41699},
    "Kasese": {"population": 1_014_158, "target_zips": 615, "start": 41700, "end": 42349},
    "Bundibugyo": {"population": 316_809, "target_zips": 192, "start": 42350, "end": 42549},
    "Ntoroko": {"population": 137_507, "target_zips": 83, "start": 42550, "end": 42649},
}
RWENZORI_VIRUNGA_GROWTH_RESERVE = (42650, 49999)


def block_capacity(record):
    return record["end"] - record["start"] + 1


def _validate_state_block(state_block, districts, reserve):
    previous_end = state_block[0] - 1
    for name, record in districts.items():
        assert record["start"] == previous_end + 1, f"gap/overlap before {name}"
        assert record["end"] <= state_block[1]
        assert block_capacity(record) >= record["target_zips"], f"insufficient capacity for {name}"
        previous_end = record["end"]
    assert previous_end + 1 == reserve[0]
    assert reserve[1] == state_block[1]
    return True


def validate_kampala_central_blocks():
    return _validate_state_block(KAMPALA_CENTRAL_BLOCK, KAMPALA_CENTRAL_DISTRICTS, KAMPALA_CENTRAL_GROWTH_RESERVE)


def validate_victoria_equatorial_blocks():
    return _validate_state_block(VICTORIA_EQUATORIAL_BLOCK, VICTORIA_EQUATORIAL_DISTRICTS, VICTORIA_EQUATORIAL_GROWTH_RESERVE)


def validate_albertine_rift_blocks():
    return _validate_state_block(ALBERTINE_RIFT_BLOCK, ALBERTINE_RIFT_DISTRICTS, ALBERTINE_RIFT_GROWTH_RESERVE)


def validate_rwenzori_virunga_blocks():
    return _validate_state_block(RWENZORI_VIRUNGA_BLOCK, RWENZORI_VIRUNGA_DISTRICTS, RWENZORI_VIRUNGA_GROWTH_RESERVE)
