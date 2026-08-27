"""UGAMAP National Special ZIP Registry.

The 00xxx family is reserved for nationally significant facilities and sites.
These codes are separate from normal geographic/state ZIP codes (20xxx-30xxx).

Memorable category anchors:
00001 State House / Presidential Residence
00002 Executive Office / Presidential Administration
00003 Diplomatic Missions & Embassies
00004 Federal Parliament
00005 Supreme Court / Federal Judiciary
00006 Federal Ministries & Departments
00007 International Organizations
00008 National Landmarks & Heritage Sites
00009 National Parks & Protected Areas
00010 Armed Forces / National Defence Institutions

Individual facilities receive codes from their category allocation blocks.
"""

SPECIAL_CATEGORY_ANCHORS = {
    "00001": {"category": "state_house", "name": "State House / Presidential Residence"},
    "00002": {"category": "executive", "name": "Executive Office / Presidential Administration"},
    "00003": {"category": "diplomatic", "name": "Diplomatic Missions & Embassies"},
    "00004": {"category": "parliament", "name": "Federal Parliament"},
    "00005": {"category": "judiciary", "name": "Supreme Court / Federal Judiciary"},
    "00006": {"category": "government", "name": "Federal Ministries & Departments"},
    "00007": {"category": "international", "name": "International Organizations"},
    "00008": {"category": "landmark", "name": "National Landmarks & Heritage Sites"},
    "00009": {"category": "parks", "name": "National Parks & Protected Areas"},
    "00010": {"category": "defence", "name": "Armed Forces / National Defence Institutions"},
}

# Facility allocation blocks. The anchor numbers above remain memorable category
# identifiers; actual facilities are assigned from these non-overlapping ranges.
SPECIAL_BLOCKS = {
    "state_house":    ("00101", "00199"),
    "executive":      ("00201", "00299"),
    "diplomatic":     ("00301", "00399"),
    "parliament":     ("00401", "00499"),
    "judiciary":      ("00501", "00599"),
    "government":     ("00601", "00699"),
    "international":  ("00701", "00799"),
    "landmark":       ("00801", "00899"),
    "parks":          ("00901", "00999"),
    "defence":        ("01001", "01099"),
}


def category_for_special_zip(zip_code: str):
    value = str(zip_code).strip().zfill(5)
    if value in SPECIAL_CATEGORY_ANCHORS:
        return SPECIAL_CATEGORY_ANCHORS[value]
    try:
        number = int(value)
    except ValueError:
        return None
    for category, (start, end) in SPECIAL_BLOCKS.items():
        if int(start) <= number <= int(end):
            return {"category": category, "range": [start, end]}
    return None


def valid_special_zip(zip_code: str) -> bool:
    return category_for_special_zip(zip_code) is not None


def special_categories():
    return [
        {"anchor": anchor, **info, "allocation_range": SPECIAL_BLOCKS[info["category"]]}
        for anchor, info in SPECIAL_CATEGORY_ANCHORS.items()
    ]
