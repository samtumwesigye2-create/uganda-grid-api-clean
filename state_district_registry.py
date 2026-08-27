"""Draft Uganda National Grid district-to-state assignment registry.

Purpose: assign district polygons to the ten custom state regions before the
geometry dissolve step. This is a DESIGN layer, not an official Ugandan
administrative classification. Automatic national address assignment must stay
disabled until the source district dataset is reconciled and geometry checks
confirm complete coverage, no overlaps, and no unassigned districts.

Entebbe's existing ZIP classifier remains authoritative in its calibrated area.
"""

# State codes correspond to state_regions.STATE_REGIONS.
# District membership is intentionally explicit so boundary changes can be
# reviewed without modifying the geometry engine.
DISTRICT_TO_STATE = {
    # Kampala Metropolitan core
    "Kampala": "KMP",
    "Wakiso": "KMP",
    "Mukono": "KMP",

    # Lake Victoria / south-central
    "Kalangala": "LKV",
    "Masaka": "LKV",
    "Kalungu": "LKV",
    "Lwengo": "LKV",
    "Bukomansimbi": "LKV",
    "Rakai": "LKV",
    "Kyotera": "LKV",

    # Nile / Busoga corridor
    "Jinja": "NIL",
    "Buikwe": "NIL",
    "Kayunga": "NIL",
    "Kamuli": "NIL",
    "Buyende": "NIL",
    "Iganga": "NIL",
    "Luuka": "NIL",
    "Mayuge": "NIL",
    "Bugiri": "NIL",
    "Namayingo": "NIL",
    "Namutumba": "NIL",
    "Kaliro": "NIL",

    # Western Highlands / south-west
    "Mbarara": "WHS",
    "Isingiro": "WHS",
    "Kiruhura": "WHS",
    "Ibanda": "WHS",
    "Bushenyi": "WHS",
    "Sheema": "WHS",
    "Buhweju": "WHS",
    "Rubirizi": "WHS",
    "Mitooma": "WHS",
    "Ntungamo": "WHS",
    "Rukungiri": "WHS",
    "Kanungu": "WHS",
    "Kabale": "WHS",
    "Rubanda": "WHS",
    "Rukiga": "WHS",
    "Kisoro": "WHS",

    # Elgon / Bugisu-Bukedi highlands
    "Mbale": "ELG",
    "Bududa": "ELG",
    "Manafwa": "ELG",
    "Namisindwa": "ELG",
    "Sironko": "ELG",
    "Bulambuli": "ELG",
    "Kapchorwa": "ELG",
    "Kween": "ELG",
    "Bukwo": "ELG",
    "Tororo": "ELG",
    "Busia": "ELG",
    "Butaleja": "ELG",
    "Budaka": "ELG",
    "Kibuku": "ELG",
    "Pallisa": "ELG",

    # Eastern Plains / Teso
    "Soroti": "EPL",
    "Serere": "EPL",
    "Kaberamaido": "EPL",
    "Kalaki": "EPL",
    "Amolatar": "EPL",
    "Kumi": "EPL",
    "Bukedea": "EPL",
    "Ngora": "EPL",
    "Katakwi": "EPL",
    "Amuria": "EPL",
    "Kapelebyong": "EPL",

    # Karamoja
    "Moroto": "KRM",
    "Napak": "KRM",
    "Nakapiripirit": "KRM",
    "Nabilatuk": "KRM",
    "Amudat": "KRM",
    "Kotido": "KRM",
    "Kaabong": "KRM",
    "Karenga": "KRM",
    "Abim": "KRM",

    # West Nile
    "Arua": "WNL",
    "Maracha": "WNL",
    "Koboko": "WNL",
    "Yumbe": "WNL",
    "Moyo": "WNL",
    "Obongi": "WNL",
    "Adjumani": "WNL",
    "Nebbi": "WNL",
    "Pakwach": "WNL",
    "Zombo": "WNL",
    "Madi-Okollo": "WNL",
    "Terego": "WNL",

    # Northern Savannah / Acholi-Lango
    "Gulu": "NSV",
    "Omoro": "NSV",
    "Amuru": "NSV",
    "Nwoya": "NSV",
    "Lamwo": "NSV",
    "Kitgum": "NSV",
    "Pader": "NSV",
    "Agago": "NSV",
    "Lira": "NSV",
    "Dokolo": "NSV",
    "Alebtong": "NSV",
    "Otuke": "NSV",
    "Apac": "NSV",
    "Kwania": "NSV",
    "Kole": "NSV",
    "Oyam": "NSV",

    # Albertine / Bunyoro-Tooro and west-central
    "Hoima": "ALB",
    "Kikuube": "ALB",
    "Buliisa": "ALB",
    "Masindi": "ALB",
    "Kiryandongo": "ALB",
    "Kagadi": "ALB",
    "Kakumiro": "ALB",
    "Kibaale": "ALB",
    "Kabarole": "ALB",
    "Bunyangabu": "ALB",
    "Ntoroko": "ALB",
    "Bundibugyo": "ALB",
    "Kamwenge": "ALB",
    "Kitagwenda": "ALB",
    "Kyenjojo": "ALB",
    "Kyegegwa": "ALB",
    "Kasese": "ALB",
    "Mubende": "ALB",
    "Kasanda": "ALB",
    "Mityana": "ALB",

    # Central districts outside the metropolitan core are provisionally split
    # between KMP/LKV pending polygon contiguity review.
    "Mpigi": "KMP",
    "Butambala": "KMP",
    "Gomba": "LKV",
    "Sembabule": "LKV",
    "Lyantonde": "LKV",

    # North-central corridor assigned to Northern Savannah for first dissolve.
    "Nakasongola": "NSV",
    "Luwero": "NSV",
    "Nakaseke": "NSV",

    # East-central corridor.
    "Kiboga": "ALB",
    "Kyankwanzi": "ALB",
}

VALID_STATE_CODES = {"KMP", "LKV", "NIL", "WHS", "ELG", "NSV", "WNL", "EPL", "KRM", "ALB"}


def state_for_district(name: str):
    return DISTRICT_TO_STATE.get(str(name).strip())


def validate_assignment(source_district_names):
    """Compare the registry with names from the source GeoJSON.

    Returns diagnostics rather than silently accepting a partial national map.
    """
    source = {str(x).strip() for x in source_district_names}
    assigned = set(DISTRICT_TO_STATE)
    invalid_states = sorted({v for v in DISTRICT_TO_STATE.values() if v not in VALID_STATE_CODES})
    return {
        "source_count": len(source),
        "assigned_count": len(assigned),
        "unassigned": sorted(source - assigned),
        "not_in_source": sorted(assigned - source),
        "invalid_state_codes": invalid_states,
        "ready_for_dissolve": not (source - assigned) and not invalid_states,
    }
