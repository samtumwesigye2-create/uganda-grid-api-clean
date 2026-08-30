"""UGAMAP / Uganda National Grid — finalized national ZIP registry.

Source of truth: finalized 5-digit ZIP architecture supplied by project owner.
ZIP codes are TEXT at API/data boundaries.

00000-09999 is the NATIONAL SPECIAL ZIP namespace. It is excluded from ordinary
state/district/residential allocation but may be assigned to approved special
facilities through the special ZIP assignment system.
"""

STATE_BLOCKS = {
 "KAMPALA_CENTRAL":{"state_name":"Kampala Central","capital":"Kampala","start":10000,"end":19999,"districts":[("Kampala (city)",10000,11399),("Wakiso",11400,13899),("Mukono",13900,14599),("Buikwe",14600,14999),("Kayunga",15000,15349),("Mpigi",15350,15599),("Butambala",15600,15749),("Gomba",15750,15899),("Mityana",15900,16199),("Mubende",16200,16599),("Luwero",16600,17049),("Nakaseke",17050,17249),("Nakasongola",17250,17449),("Kiboga",17450,17649),("Kyankwanzi",17650,17899),("Buvuma (islands)",17900,17999)]},
 "VICTORIA_EQUATORIAL":{"state_name":"Victoria Equatorial","capital":"Masaka","start":20000,"end":29999,"districts":[("Masaka (district)",20000,20099),("Masaka City",20100,20249),("Kalungu",20250,20449),("Bukomansimbi",20450,20599),("Lwengo",20600,20849),("Ssembabule",20850,21099),("Lyantonde",21100,21199),("Rakai",21200,21449),("Kyotera",21450,21699),("Kalangala (islands)",21700,21799)]},
 "ALBERTINE_RIFT":{"state_name":"Albertine Rift","capital":"Hoima","start":30000,"end":32249,"shared_block":3,"districts":[("Hoima District",30000,30199),("Hoima City",30200,30349),("Kibaale",30350,30549),("Masindi",30550,30799),("Buliisa",30800,30949),("Kiryandongo",30950,31249),("Kagadi",31250,31599),("Kakumiro",31600,31949),("Kikuube",31950,32249)]},
 "WEST_NILE":{"state_name":"West Nile","capital":"Arua","start":32250,"end":35349,"shared_block":3,"districts":[("Adjumani",32250,32499),("Arua District",32500,32649),("Arua City",32650,32899),("Moyo",32900,32999),("Nebbi",33000,33249),("Yumbe",33250,33999),("Koboko",34000,34199),("Maracha",34200,34399),("Zombo",34400,34649),("Pakwach",34650,34799),("Madi-Okollo",34800,34949),("Obongi",34950,35099),("Terego",35100,35349)]},
 "RWENZORI_VIRUNGA":{"state_name":"Rwenzori Virunga","capital":"Fort Portal","start":40000,"end":49999,"districts":[("Kabarole",40000,40199),("Fort Portal City",40200,40299),("Bunyangabu",40300,40499),("Kamwenge",40500,40749),("Kitagwenda",40750,40899),("Kyegegwa",40900,41299),("Kyenjojo",41300,41699),("Kasese",41700,42349),("Bundibugyo",42350,42549),("Ntoroko",42550,42649)]},
 "KATONGA_HIGHLAND":{"state_name":"Katonga Highland","capital":"Mbarara","start":50000,"end":59999,"districts":[("Buhweju",50000,50149),("Bushenyi",50150,50399),("Ibanda",50400,50649),("Isingiro",50650,51149),("Kazo",51150,51349),("Kiruhura",51350,51549),("Mbarara District",51550,51699),("Mbarara City",51700,51899),("Mitooma",51900,52099),("Ntungamo",52100,52549),("Rubirizi",52550,52699),("Rwampara",52700,52849),("Sheema",52850,53049),("Kabale",53050,53299),("Kisoro",53300,53649),("Rukungiri",53650,53949),("Kanungu",53950,54199),("Rubanda",54200,54399),("Rukiga",54400,54449)]},
 "NILE_SOURCE":{"state_name":"Nile Source","capital":"Jinja","start":60000,"end":69999,"districts":[("Bugiri",60000,60399),("Iganga",60400,60749),("Jinja District",60750,60999),("Jinja City",61000,61249),("Kamuli",61250,61649),("Mayuge",61650,62099),("Kaliro",62100,62349),("Namutumba",62350,62599),("Buyende",62600,62899),("Luuka",62900,63149),("Namayingo",63150,63349),("Bugweri",63350,63549)]},
 "ELGON_KARAMOJA":{"state_name":"Elgon Karamoja","capital":"Mbale","start":70000,"end":79999,"districts":[("Sironko",70000,70249),("Bududa",70250,70499),("Bukwo",70500,70599),("Manafwa",70600,70749),("Bulambuli",70750,70949),("Kween",70950,71099),("Namisindwa",71100,71299),("Mbale City",71300,71549),("Mbale District",71550,71899),("Kotido",71900,72099),("Moroto",72100,72199),("Nakapiripirit",72200,72299),("Abim",72300,72449),("Kaabong",72450,72649),("Amudat",72650,72799),("Napak",72800,72999),("Nabilatuk",73000,73149),("Karenga",73150,73249)]},
 "KYOGA_KWANIA":{"state_name":"Kyoga Kwania","capital":"Soroti","start":80000,"end":89999,"districts":[("Kumi",80000,80249),("Serere",80250,80549),("Kaberamaido",80550,80699),("Soroti District",80700,80899),("Soroti City",80900,80999),("Kalaki",81000,81149),("Amuria",81150,81349),("Bukedea",81350,81599),("Katakwi",81600,81799),("Ngora",81800,82099),("Busia",82100,82399),("Pallisa",82400,82649),("Tororo",82650,83099),("Budaka",83100,83299),("Butaleja",83300,83549),("Kibuku",83550,83749),("Butebo",83750,83899)]},
 "ASWA_SAVANNAH":{"state_name":"Aswa Savannah","capital":"Gulu","start":90000,"end":99999,"districts":[("Gulu District",90000,90099),("Gulu City",90100,90349),("Kitgum",90350,90549),("Pader",90550,90749),("Amuru",90750,90949),("Agago",90950,91199),("Lamwo",91200,91399),("Nwoya",91400,91599),("Omoro",91600,91799),("Apac",91800,91999),("Lira District",92000,92199),("Amolatar",92200,92399),("Dokolo",92400,92599),("Oyam",92600,92949),("Alebtong",92950,93199),("Kole",93200,93449),("Otuke",93450,93599),("Kwania",93600,93799),("Lira City",93800,93999)]}
}

SPECIAL_ZIP_BLOCK=(0,9999)
SHARED_RESERVED=[(35350,39999)]
DATA_GAPS=["Kalangala (islands)","Kiboga","Kyotera","Masaka City","Mbale District","Ngora"]
COUNTY_SUBSPLIT=["Wakiso","Kasese","Yumbe"]


def _norm(z):
 s=str(z).strip()
 if not s.isdigit() or len(s)>5:return None
 return int(s.zfill(5))

def _fmt(n):return f"{n:05d}"

def lookup_zip(zip_code):
 n=_norm(zip_code)
 if n is None:return None
 if 0<=n<=9999:return {"zip_code":_fmt(n),"reserved":False,"special_only":True,"ordinary_assignment_allowed":False,"namespace":"national_special_zip","state_name":None,"district":None}
 if 35350<=n<=39999:return {"zip_code":_fmt(n),"reserved":True,"reservation":"shared_block_3_growth","state_name":None,"district":None,"shared_by":["Albertine Rift","West Nile"]}
 for key,s in STATE_BLOCKS.items():
  if s["start"]<=n<=s["end"]:
   for name,a,b in s["districts"]:
    if a<=n<=b:return {"zip_code":_fmt(n),"reserved":False,"special_only":False,"ordinary_assignment_allowed":True,"state_key":key,"state_name":s["state_name"],"political_region":s["state_name"],"capital":s["capital"],"district":name,"district_range":f"{_fmt(a)}-{_fmt(b)}","data_gap":name in DATA_GAPS,"county_subsplit_flag":name in COUNTY_SUBSPLIT}
   return {"zip_code":_fmt(n),"reserved":True,"special_only":False,"ordinary_assignment_allowed":False,"reservation":"state_growth","state_key":key,"state_name":s["state_name"],"political_region":s["state_name"],"capital":s["capital"],"district":None}
 return None

def state_summary(state_key):
 s=STATE_BLOCKS.get(str(state_key).strip().upper())
 if not s:return None
 assigned=sum(b-a+1 for _,a,b in s["districts"]);capacity=s["end"]-s["start"]+1
 return {"state_key":str(state_key).strip().upper(),"state_name":s["state_name"],"capital":s["capital"],"range":f"{_fmt(s['start'])}-{_fmt(s['end'])}","capacity":capacity,"assigned":assigned,"reserved":capacity-assigned,"utilization_percent":round(100*assigned/capacity,1),"district_count":len(s["districts"]),"districts":[{"district":n,"start":_fmt(a),"end":_fmt(b),"codes":b-a+1,"data_gap":n in DATA_GAPS,"county_subsplit_flag":n in COUNTY_SUBSPLIT} for n,a,b in s["districts"]]}

def validate_registry():
 errors=[];ranges=[];districts=0
 for key,s in STATE_BLOCKS.items():
  for name,a,b in s["districts"]:
   districts+=1
   if a>b or a<s["start"] or b>s["end"]:errors.append(f"{key}/{name}: invalid range")
   ranges.append((a,b,key,name))
 ranges.sort()
 for p,c in zip(ranges,ranges[1:]):
  if c[0]<=p[1]:errors.append(f"overlap: {p[3]} / {c[3]}")
 return {"valid":not errors,"errors":errors,"states_loaded":len(STATE_BLOCKS),"district_rows_loaded":districts,"zip_storage":"TEXT","special_zip_block":"00000-09999","special_zip_policy":"special facilities only; excluded from ordinary state/district/residential assignment","shared_block_3_reserved":"35350-39999","data_gaps":DATA_GAPS,"county_subsplit_flags":COUNTY_SUBSPLIT}
