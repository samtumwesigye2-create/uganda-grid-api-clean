"""District-level population lookup for population-weighted ZIP geometry.

Source: Uganda Bureau of Statistics 2023 district population estimates
(Wikipedia "Districts of Uganda" per-district tables), keyed with the exact
district-name strings used in state_district_registry.DISTRICT_TO_STATE so
lookups line up with the same source geometry without name-matching guesswork.

Used only to decide WHERE to cut a state's land into ZIP polygons (dense
areas get cut more finely than sparse ones). It is not a replacement for
real sub-district/parish population data — within a single district, this
still assumes population is spread evenly across its area, since no finer
data is wired in yet.
"""

DISTRICT_POPULATION_2023 = {
    "Buikwe": 499800, "Bukomansimbi": 158400, "Butambala": 110900, "Buvuma": 154200,
    "Gomba": 180300, "Kalangala": 74500, "Kalungu": 189200, "Kampala": 1766500,
    "Kassanda": 334100, "Kayunga": 427100, "Kiboga": 183300, "Kyankwanzi": 323900,
    "Kyotera": 271100, "Luwero": 558100, "Lwengo": 297200, "Lyantonde": 119600,
    "Masaka": 364800, "Mityana": 378800, "Mpigi": 305300, "Mubende": 641800,
    "Mukono": 757500, "Nakaseke": 254900, "Nakasongola": 233400, "Rakai": 338900,
    "Sembabule": 319300, "Wakiso": 3519300,
    "Amuria": 248500, "Budaka": 278600, "Bududa": 307200, "Bugiri": 536400,
    "Bugweri": 205600, "Bukedea": 291800, "Bukwo": 137200, "Bulambuli": 264500,
    "Busia": 416700, "Butaleja": 332200, "Butebo": 125700, "Buyende": 468400,
    "Iganga": 436800, "Jinja": 535800, "Kaberamaido": 148700, "Kalaki": 155400,
    "Kaliro": 317900, "Kamuli": 596100, "Kapchorwa": 133900, "Kapelebyong": 112500,
    "Katakwi": 209700, "Kibuku": 278200, "Kumi": 309500, "Kween": 118000,
    "Luuka": 281600, "Manafwa": 186300, "Mayuge": 615200, "Mbale": 639700,
    "Namayingo": 247400, "Namisindwa": 247900, "Namutumba": 336400, "Ngora": 178400,
    "Pallisa": 399500, "Serere": 401800, "Sironko": 290500, "Soroti": 401000,
    "Tororo": 639700,
    "Abim": 182800, "Adjumani": 240000, "Agago": 262500, "Alebtong": 286400,
    "Amolatar": 182000, "Amudat": 151900, "Amuru": 232500, "Apac": 249600,
    "Arua": 557900, "Dokolo": 232900, "Gulu": 352500, "Kaabong": 134400,
    "Karenga": 73100, "Kitgum": 232900, "Koboko": 287500, "Kole": 308800,
    "Kotido": 219700, "Kwania": 234600, "Lamwo": 148100, "Lira": 516000,
    "Madi-Okollo": 176800, "Maracha": 219500, "Moroto": 126300, "Moyo": 116400,
    "Nabilatuk": 102500, "Nakapiripirit": 128100, "Napak": 166200, "Nebbi": 306300,
    "Nwoya": 314300, "Obongi": 52300, "Omoro": 216400, "Otuke": 150600,
    "Oyam": 491600, "Pader": 206700, "Pakwach": 219000, "Terego": 251500,
    "Yumbe": 775000, "Zombo": 306100,
    "Buhweju": 156900, "Buliisa": 171300, "Bundibugyo": 285000, "Bunyangabu": 208000,
    "Bushenyi": 254200, "Hoima": 413100, "Ibanda": 290900, "Isingiro": 658100,
    "Kabale": 256900, "Kabarole": 357500, "Kagadi": 474700, "Kakumiro": 601900,
    "Kamwenge": 372000, "Kanungu": 235400, "Kasese": 843900, "Kazo": 240400,
    "Kibaale": 234800, "Kikuube": 414400, "Kiruhura": 205300, "Kiryandongo": 339200,
    "Kisoro": 332200, "Kitagwenda": 197800, "Kyegegwa": 551900, "Kyenjojo": 584400,
    "Masindi": 366900, "Mbarara": 414000, "Mitooma": 198900, "Ntoroko": 80700,
    "Ntungamo": 569200, "Rubanda": 213400, "Rubirizi": 151500, "Rukiga": 107200,
    "Rukungiri": 342000, "Rwampara": 153100, "Sheema": 226300,
}


def population_for_district(name: str) -> float:
    """Return the district's population estimate, or 0.0 if unknown.

    A missing/unmatched name falls back to 0 rather than raising, so a
    geometry-source spelling we haven't seen doesn't crash ZIP generation —
    it just won't get prioritized for finer splitting.
    """
    return float(DISTRICT_POPULATION_2023.get(str(name).strip(), 0.0))
