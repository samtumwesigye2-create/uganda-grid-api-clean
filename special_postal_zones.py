"""UGAMAP National Special ZIP Registry.

00xxx is reserved for nationally significant facilities. Each memorable anchor
has a matching sub-series so codes stay easy to recognize:
00001 State House; 00011-00019 additional State Houses
00002 Executive; 00021-00029 executive facilities
00003 Diplomatic; 00031-00039 diplomatic facilities
00004 Parliament; 00041-00049 parliamentary facilities
00005 Judiciary; 00051-00059 judiciary facilities
00006 Government; 00061-00069 ministries/departments
00007 International; 00071-00079 international organizations
00008 Landmarks; 00081-00089 landmarks/heritage
00009 Parks; 00091-00099 parks/protected areas
00010 Defence; 00101-00109 defence institutions
"""
SPECIAL_CATEGORY_ANCHORS={
 "00001":{"category":"state_house","name":"State House / Presidential Residence"},
 "00002":{"category":"executive","name":"Executive Office / Presidential Administration"},
 "00003":{"category":"diplomatic","name":"Diplomatic Missions & Embassies"},
 "00004":{"category":"parliament","name":"Parliament / Legislature"},
 "00005":{"category":"judiciary","name":"Supreme Court / Judiciary"},
 "00006":{"category":"government","name":"Ministries & Government Departments"},
 "00007":{"category":"international","name":"International Organizations"},
 "00008":{"category":"landmark","name":"National Landmarks & Heritage Sites"},
 "00009":{"category":"parks","name":"National Parks & Protected Areas"},
 "00010":{"category":"defence","name":"Armed Forces / National Defence Institutions"},
}
SPECIAL_BLOCKS={
 "state_house":("00011","00019"),
 "executive":("00021","00029"),
 "diplomatic":("00031","00039"),
 "parliament":("00041","00049"),
 "judiciary":("00051","00059"),
 "government":("00061","00069"),
 "international":("00071","00079"),
 "landmark":("00081","00089"),
 "parks":("00091","00099"),
 "defence":("00101","00109"),
}
def category_for_special_zip(zip_code:str):
 value=str(zip_code).strip().zfill(5)
 if value in SPECIAL_CATEGORY_ANCHORS:return SPECIAL_CATEGORY_ANCHORS[value]
 try:number=int(value)
 except ValueError:return None
 for category,(start,end) in SPECIAL_BLOCKS.items():
  if int(start)<=number<=int(end):return {"category":category,"range":[start,end]}
 return None
def valid_special_zip(zip_code:str)->bool:return category_for_special_zip(zip_code) is not None
def special_categories():return [{"anchor":anchor,**info,"allocation_range":SPECIAL_BLOCKS[info["category"]]} for anchor,info in SPECIAL_CATEGORY_ANCHORS.items()]
