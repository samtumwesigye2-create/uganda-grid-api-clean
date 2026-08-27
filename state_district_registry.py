"""Uganda National Grid district-to-state assignment registry.

All 136 current district-tier units are explicitly assigned to one of the ten
custom state regions. This is a DESIGN layer, not an official Ugandan
administrative classification. Geometry validation must still confirm complete
coverage, no overlaps, and no unassigned polygons before automatic national
address assignment is enabled.

Entebbe's existing ZIP classifier remains authoritative in its calibrated area.
"""

DISTRICT_TO_STATE = {
    # Kampala Metropolitan
    "Kampala": "KMP", "Wakiso": "KMP", "Mukono": "KMP", "Mpigi": "KMP", "Butambala": "KMP",

    # Lake Victoria / south-central
    "Kalangala": "LKV", "Masaka": "LKV", "Kalungu": "LKV", "Lwengo": "LKV", "Bukomansimbi": "LKV",
    "Rakai": "LKV", "Kyotera": "LKV", "Gomba": "LKV", "Sembabule": "LKV", "Lyantonde": "LKV",

    # Nile / Busoga corridor
    "Jinja": "NIL", "Buikwe": "NIL", "Buvuma": "NIL", "Kayunga": "NIL", "Kamuli": "NIL", "Buyende": "NIL",
    "Iganga": "NIL", "Bugweri": "NIL", "Luuka": "NIL", "Mayuge": "NIL", "Bugiri": "NIL", "Namayingo": "NIL",
    "Namutumba": "NIL", "Kaliro": "NIL",

    # Western Highlands / south-west
    "Mbarara": "WHS", "Rwampara": "WHS", "Isingiro": "WHS", "Kiruhura": "WHS", "Kazo": "WHS", "Ibanda": "WHS",
    "Bushenyi": "WHS", "Sheema": "WHS", "Buhweju": "WHS", "Rubirizi": "WHS", "Mitooma": "WHS", "Ntungamo": "WHS",
    "Rukungiri": "WHS", "Kanungu": "WHS", "Kabale": "WHS", "Rubanda": "WHS", "Rukiga": "WHS", "Kisoro": "WHS",

    # Elgon / Bugisu-Bukedi highlands
    "Mbale": "ELG", "Bududa": "ELG", "Manafwa": "ELG", "Namisindwa": "ELG", "Sironko": "ELG", "Bulambuli": "ELG",
    "Kapchorwa": "ELG", "Kween": "ELG", "Bukwo": "ELG", "Tororo": "ELG", "Busia": "ELG", "Butaleja": "ELG",
    "Budaka": "ELG", "Kibuku": "ELG", "Pallisa": "ELG", "Butebo": "ELG",

    # Eastern Plains / Teso
    "Soroti": "EPL", "Serere": "EPL", "Kaberamaido": "EPL", "Kalaki": "EPL", "Amolatar": "EPL", "Kumi": "EPL",
    "Bukedea": "EPL", "Ngora": "EPL", "Katakwi": "EPL", "Amuria": "EPL", "Kapelebyong": "EPL",

    # Karamoja
    "Moroto": "KRM", "Napak": "KRM", "Nakapiripirit": "KRM", "Nabilatuk": "KRM", "Amudat": "KRM",
    "Kotido": "KRM", "Kaabong": "KRM", "Karenga": "KRM", "Abim": "KRM",

    # West Nile
    "Arua": "WNL", "Maracha": "WNL", "Koboko": "WNL", "Yumbe": "WNL", "Moyo": "WNL", "Obongi": "WNL",
    "Adjumani": "WNL", "Nebbi": "WNL", "Pakwach": "WNL", "Zombo": "WNL", "Madi-Okollo": "WNL", "Terego": "WNL",

    # Northern Savannah / Acholi-Lango + north-central corridor
    "Gulu": "NSV", "Omoro": "NSV", "Amuru": "NSV", "Nwoya": "NSV", "Lamwo": "NSV", "Kitgum": "NSV",
    "Pader": "NSV", "Agago": "NSV", "Lira": "NSV", "Dokolo": "NSV", "Alebtong": "NSV", "Otuke": "NSV",
    "Apac": "NSV", "Kwania": "NSV", "Kole": "NSV", "Oyam": "NSV", "Nakasongola": "NSV", "Luwero": "NSV",
    "Nakaseke": "NSV",

    # Albertine / Bunyoro-Tooro and west-central
    "Hoima": "ALB", "Kikuube": "ALB", "Buliisa": "ALB", "Masindi": "ALB", "Kiryandongo": "ALB", "Kagadi": "ALB",
    "Kakumiro": "ALB", "Kibaale": "ALB", "Kabarole": "ALB", "Bunyangabu": "ALB", "Ntoroko": "ALB",
    "Bundibugyo": "ALB", "Kamwenge": "ALB", "Kitagwenda": "ALB", "Kyenjojo": "ALB", "Kyegegwa": "ALB",
    "Kasese": "ALB", "Mubende": "ALB", "Kassanda": "ALB", "Mityana": "ALB", "Kiboga": "ALB", "Kyankwanzi": "ALB",
}

VALID_STATE_CODES = {"KMP", "LKV", "NIL", "WHS", "ELG", "NSV", "WNL", "EPL", "KRM", "ALB"}
EXPECTED_DISTRICT_COUNT = 136


def state_for_district(name: str):
    return DISTRICT_TO_STATE.get(str(name).strip())


def validate_assignment(source_district_names):
    """Compare the registry with names from the authoritative source dataset."""
    source = {str(x).strip() for x in source_district_names}
    assigned = set(DISTRICT_TO_STATE)
    invalid_states = sorted({v for v in DISTRICT_TO_STATE.values() if v not in VALID_STATE_CODES})
    unassigned = sorted(source - assigned)
    not_in_source = sorted(assigned - source)
    return {
        "source_count": len(source),
        "assigned_count": len(assigned),
        "expected_district_count": EXPECTED_DISTRICT_COUNT,
        "unassigned": unassigned,
        "not_in_source": not_in_source,
        "invalid_state_codes": invalid_states,
        "ready_for_dissolve": (
            len(source) == EXPECTED_DISTRICT_COUNT
            and len(assigned) == EXPECTED_DISTRICT_COUNT
            and not unassigned
            and not not_in_source
            and not invalid_states
        ),
    }
