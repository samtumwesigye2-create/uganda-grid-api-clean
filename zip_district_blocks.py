"""District-level ZIP capacity registry for UGAMAP.

These are capacity reservations, not live ZIP issuance. Existing ZIP codes and
polygons remain authoritative until an explicit migration is performed.
"""

# Prefix 0 is reserved for national/special-purpose ZIPs. Ordinary geographic
# addresses use prefixes 1-9 so they never depend on preserving a leading zero.
NATIONAL_SPECIAL_BLOCK = (0, 9999)
NATIONAL_SPECIAL_STATUS = "reserved_non_geographic"

KAMPALA_CENTRAL_BLOCK = (10000, 19999)
VICTORIA_EQUATORIAL_BLOCK = (20000, 29999)
ALBERTINE_WEST_NILE_SHARED_BLOCK = (30000, 39999)
ALBERTINE_RIFT_BLOCK = (30000, 32249)
WEST_NILE_BLOCK = (32250, 35399)
ALBERTINE_WEST_NILE_GROWTH_RESERVE = (35400, 39999)
RWENZORI_VIRUNGA_BLOCK = (40000, 49999)
KATONGA_HIGHLAND_BLOCK = (50000, 59999)
NILE_SOURCE_BLOCK = (60000, 69999)
ELGON_KARAMOJA_BLOCK = (70000, 79999)
KYOGA_KWANIA_BLOCK = (80000, 89999)
ASWA_SAVANNAH_BLOCK = (90000, 99999)

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

WEST_NILE_DISTRICTS = {
    "Adjumani": {"start": 32250, "end": 32499},
    "Arua District": {"start": 32500, "end": 32649},
    "Arua City": {"start": 32650, "end": 32949},
    "Moyo": {"start": 32950, "end": 33049},
    "Nebbi": {"start": 33050, "end": 33299},
    "Yumbe": {"start": 33300, "end": 34049},
    "Koboko": {"start": 34050, "end": 34249},
    "Maracha": {"start": 34250, "end": 34449},
    "Zombo": {"start": 34450, "end": 34699},
    "Pakwach": {"start": 34700, "end": 34849},
    "Madi-Okollo": {"start": 34850, "end": 34999},
    "Obongi": {"start": 35000, "end": 35149},
    "Terego": {"start": 35150, "end": 35399},
}

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

KATONGA_HIGHLAND_DISTRICTS = {
    "Buhweju": {"start": 50000, "end": 50149}, "Bushenyi": {"start": 50150, "end": 50399},
    "Ibanda": {"start": 50400, "end": 50649}, "Isingiro": {"start": 50650, "end": 51149},
    "Kazo": {"start": 51150, "end": 51349}, "Kiruhura": {"start": 51350, "end": 51499},
    "Mbarara District": {"start": 51500, "end": 51649}, "Mbarara City": {"start": 51650, "end": 51849},
    "Mitooma": {"start": 51850, "end": 52049}, "Ntungamo": {"start": 52050, "end": 52499},
    "Rubirizi": {"start": 52500, "end": 52649}, "Rwampara": {"start": 52650, "end": 52799},
    "Sheema": {"start": 52800, "end": 52999}, "Kabale": {"start": 53000, "end": 53249},
    "Kisoro": {"start": 53250, "end": 53599}, "Rukungiri": {"start": 53600, "end": 53899},
    "Kanungu": {"start": 53900, "end": 54149}, "Rubanda": {"start": 54150, "end": 54349},
    "Rukiga": {"start": 54350, "end": 54449},
}
KATONGA_HIGHLAND_GROWTH_RESERVE = (54450, 59999)

NILE_SOURCE_DISTRICTS = {
    "Bugiri": {"start": 60000, "end": 60399}, "Iganga": {"start": 60400, "end": 60749},
    "Jinja District": {"start": 60750, "end": 60999}, "Jinja City": {"start": 61000, "end": 61249},
    "Kamuli": {"start": 61250, "end": 61649}, "Mayuge": {"start": 61650, "end": 62099},
    "Kaliro": {"start": 62100, "end": 62349}, "Namutumba": {"start": 62350, "end": 62599},
    "Buyende": {"start": 62600, "end": 62899}, "Luuka": {"start": 62900, "end": 63149},
    "Namayingo": {"start": 63150, "end": 63349}, "Bugweri": {"start": 63350, "end": 63549},
}
NILE_SOURCE_GROWTH_RESERVE = (63550, 69999)

ELGON_KARAMOJA_DISTRICTS = {
    "Sironko": {"start": 70000, "end": 70249}, "Bududa": {"start": 70250, "end": 70499},
    "Bukwo": {"start": 70500, "end": 70599}, "Manafwa": {"start": 70600, "end": 70749},
    "Bulambuli": {"start": 70750, "end": 70949}, "Kween": {"start": 70950, "end": 71049},
    "Namisindwa": {"start": 71050, "end": 71249}, "Mbale City": {"start": 71250, "end": 71499},
    "Mbale District": {"start": 71500, "end": 71849}, "Kotido": {"start": 71850, "end": 72049},
    "Moroto": {"start": 72050, "end": 72149}, "Nakapiripirit": {"start": 72150, "end": 72249},
    "Abim": {"start": 72250, "end": 72399}, "Kaabong": {"start": 72400, "end": 72599},
    "Amudat": {"start": 72600, "end": 72749}, "Napak": {"start": 72750, "end": 72949},
    "Nabilatuk": {"start": 72950, "end": 73099}, "Karenga": {"start": 73100, "end": 73199},
}
ELGON_KARAMOJA_GROWTH_RESERVE = (73200, 79999)

KYOGA_KWANIA_DISTRICTS = {
    "Kumi": {"start": 80000, "end": 80249}, "Serere": {"start": 80250, "end": 80549},
    "Kaberamaido": {"start": 80550, "end": 80699}, "Soroti District": {"start": 80700, "end": 80899},
    "Soroti City": {"start": 80900, "end": 80999}, "Kalaki": {"start": 81000, "end": 81149},
    "Amuria": {"start": 81150, "end": 81349}, "Bukedea": {"start": 81350, "end": 81599},
    "Katakwi": {"start": 81600, "end": 81799}, "Ngora": {"start": 81800, "end": 82099},
    "Bukedi Combined": {"start": 82100, "end": 83849, "status": "pending_7_district_split"},
}
KYOGA_KWANIA_GROWTH_RESERVE = (83850, 89999)

ASWA_SAVANNAH_DISTRICTS = {
    "Gulu": {"start": 90000, "end": 90099}, "Gulu City": {"start": 90100, "end": 90299},
    "Kitgum": {"start": 90300, "end": 90499}, "Pader": {"start": 90500, "end": 90699},
    "Amuru": {"start": 90700, "end": 90899}, "Agago": {"start": 90900, "end": 91149},
    "Lamwo": {"start": 91150, "end": 91349}, "Nwoya": {"start": 91350, "end": 91549},
    "Omoro": {"start": 91550, "end": 91699}, "Apac": {"start": 91700, "end": 91899},
    "Lira District": {"start": 91900, "end": 92099}, "Amolatar": {"start": 92100, "end": 92249},
    "Dokolo": {"start": 92250, "end": 92449}, "Oyam": {"start": 92450, "end": 92799},
    "Alebtong": {"start": 92800, "end": 93049}, "Kole": {"start": 93050, "end": 93299},
    "Otuke": {"start": 93300, "end": 93449}, "Kwania": {"start": 93450, "end": 93649},
    "Lira City": {"start": 93650, "end": 93849},
}
ASWA_SAVANNAH_GROWTH_RESERVE = (93850, 99999)


def block_capacity(record):
    return record["end"] - record["start"] + 1


def _validate_state_block(state_block, districts, reserve, require_targets=False):
    previous_end = state_block[0] - 1
    for name, record in districts.items():
        assert record["start"] == previous_end + 1, f"gap/overlap before {name}"
        assert record["end"] <= state_block[1]
        if require_targets and "target_zips" in record:
            assert block_capacity(record) >= record["target_zips"], f"insufficient capacity for {name}"
        previous_end = record["end"]
    assert previous_end + 1 == reserve[0]
    assert reserve[1] == state_block[1]
    return True


def _validate_contiguous_block(block, districts):
    previous_end = block[0] - 1
    for name, record in districts.items():
        assert record["start"] == previous_end + 1, f"gap/overlap before {name}"
        assert record["end"] <= block[1]
        previous_end = record["end"]
    assert previous_end == block[1]
    return True


def validate_kampala_central_blocks(): return _validate_state_block(KAMPALA_CENTRAL_BLOCK, KAMPALA_CENTRAL_DISTRICTS, KAMPALA_CENTRAL_GROWTH_RESERVE, True)
def validate_victoria_equatorial_blocks(): return _validate_state_block(VICTORIA_EQUATORIAL_BLOCK, VICTORIA_EQUATORIAL_DISTRICTS, VICTORIA_EQUATORIAL_GROWTH_RESERVE, True)
def validate_albertine_rift_blocks(): return _validate_contiguous_block(ALBERTINE_RIFT_BLOCK, ALBERTINE_RIFT_DISTRICTS)
def validate_west_nile_blocks(): return _validate_contiguous_block(WEST_NILE_BLOCK, WEST_NILE_DISTRICTS)
def validate_albertine_west_nile_shared_block():
    assert ALBERTINE_RIFT_BLOCK[0] == ALBERTINE_WEST_NILE_SHARED_BLOCK[0]
    assert ALBERTINE_RIFT_BLOCK[1] + 1 == WEST_NILE_BLOCK[0]
    assert WEST_NILE_BLOCK[1] + 1 == ALBERTINE_WEST_NILE_GROWTH_RESERVE[0]
    assert ALBERTINE_WEST_NILE_GROWTH_RESERVE[1] == ALBERTINE_WEST_NILE_SHARED_BLOCK[1]
    return True

def validate_rwenzori_virunga_blocks(): return _validate_state_block(RWENZORI_VIRUNGA_BLOCK, RWENZORI_VIRUNGA_DISTRICTS, RWENZORI_VIRUNGA_GROWTH_RESERVE, True)
def validate_katonga_highland_blocks(): return _validate_state_block(KATONGA_HIGHLAND_BLOCK, KATONGA_HIGHLAND_DISTRICTS, KATONGA_HIGHLAND_GROWTH_RESERVE)
def validate_nile_source_blocks(): return _validate_state_block(NILE_SOURCE_BLOCK, NILE_SOURCE_DISTRICTS, NILE_SOURCE_GROWTH_RESERVE)
def validate_elgon_karamoja_blocks(): return _validate_state_block(ELGON_KARAMOJA_BLOCK, ELGON_KARAMOJA_DISTRICTS, ELGON_KARAMOJA_GROWTH_RESERVE)
def validate_kyoga_kwania_blocks(): return _validate_state_block(KYOGA_KWANIA_BLOCK, KYOGA_KWANIA_DISTRICTS, KYOGA_KWANIA_GROWTH_RESERVE)
def validate_aswa_savannah_blocks(): return _validate_state_block(ASWA_SAVANNAH_BLOCK, ASWA_SAVANNAH_DISTRICTS, ASWA_SAVANNAH_GROWTH_RESERVE)
