"""UGAMAP National Special ZIP Registry.

00000-09999 is the National Special ZIP namespace. These codes are TEXT and may
only be assigned to approved special-purpose facilities; ordinary residential,
district, and village-cluster assignment must never allocate from this block.

00000 itself remains unassigned as the namespace marker. Category blocks are
intentionally spacious so nationally significant facilities can expand without
colliding with ordinary state ZIP allocations.
"""

SPECIAL_NAMESPACE=("00000","09999")
UNASSIGNED_NAMESPACE_MARKER="00000"

SPECIAL_CATEGORY_ANCHORS={
 "00001":{"category":"state_house","name":"State House / Presidential Residences"},
 "00002":{"category":"executive","name":"Executive Offices & Presidential Administration"},
 "00003":{"category":"diplomatic","name":"Diplomatic Missions & Embassies"},
 "00004":{"category":"parliament","name":"Parliament / Legislature"},
 "00005":{"category":"judiciary","name":"National Judiciary"},
 "00006":{"category":"government","name":"Federal Ministries, Departments & Agencies"},
 "00007":{"category":"international","name":"International Organizations"},
 "00008":{"category":"landmark","name":"National Landmarks & Heritage Sites"},
 "00009":{"category":"parks","name":"National Parks & Protected Areas"},
 "00010":{"category":"defence","name":"Armed Forces & National Defence Institutions"},
 "00020":{"category":"airport","name":"Airports & Aviation Facilities"},
 "00030":{"category":"port","name":"Ports, Harbours & Strategic Ferry Terminals"},
 "00040":{"category":"hospital","name":"National & Referral Hospitals"},
 "00050":{"category":"security","name":"National Security & Emergency Institutions"},
 "00060":{"category":"university","name":"National Universities & Research Institutions"},
 "00070":{"category":"postal_logistics","name":"National Postal & Logistics Hubs"},
 "00080":{"category":"utility","name":"Strategic Utilities & Infrastructure"},
 "00090":{"category":"reserve_special","name":"Special ZIP Administrative Reserve"},
}

SPECIAL_BLOCKS={
 "state_house":("00100","00149"),
 "executive":("00150","00199"),
 "diplomatic":("00200","00999"),
 "parliament":("01000","01099"),
 "judiciary":("01100","01199"),
 "government":("01200","01999"),
 "international":("02000","02499"),
 "landmark":("02500","02999"),
 "parks":("03000","03999"),
 "defence":("04000","04999"),
 "airport":("05000","05499"),
 "port":("05500","05999"),
 "hospital":("06000","06499"),
 "security":("06500","06999"),
 "university":("07000","07499"),
 "postal_logistics":("07500","07999"),
 "utility":("08000","08499"),
 "reserve_special":("08500","09999"),
}

# Legacy compact series remain valid so existing special assignments are not broken.
LEGACY_SPECIAL_RANGES={
 "state_house":[("00011","00019")],
 "executive":[("00021","00029")],
 "diplomatic":[("00031","00039")],
 "parliament":[("00041","00049")],
 "judiciary":[("00051","00059")],
 "government":[("00061","00069"),("00601","00699")],
 "international":[("00071","00079")],
 "landmark":[("00081","00089")],
 "parks":[("00091","00099")],
 "defence":[("00101","00109")],
}


def category_for_special_zip(zip_code:str):
 value=str(zip_code).strip().zfill(5)
 if not value.isdigit() or len(value)!=5 or value==UNASSIGNED_NAMESPACE_MARKER:return None
 if value in SPECIAL_CATEGORY_ANCHORS:return SPECIAL_CATEGORY_ANCHORS[value]
 number=int(value)
 for category,ranges in LEGACY_SPECIAL_RANGES.items():
  for start,end in ranges:
   if int(start)<=number<=int(end):return {"category":category,"range":[start,end],"legacy":True}
 for category,(start,end) in SPECIAL_BLOCKS.items():
  if int(start)<=number<=int(end):return {"category":category,"range":[start,end],"legacy":False}
 return None


def valid_special_zip(zip_code:str)->bool:return category_for_special_zip(zip_code) is not None


def special_categories():
 result=[]
 for anchor,info in SPECIAL_CATEGORY_ANCHORS.items():
  category=info["category"]
  result.append({"anchor":anchor,**info,"allocation_range":SPECIAL_BLOCKS[category],"legacy_ranges":LEGACY_SPECIAL_RANGES.get(category,[])})
 return result


def namespace_summary():
 return {"namespace":"00000-09999","storage":"TEXT","ordinary_address_assignment":False,"special_assignment":True,"unassigned_marker":"00000","categories":special_categories()}
