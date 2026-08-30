"""Uganda National Grid postal-zone registry.

Postal allocation keeps the existing ZIP prefixes and locations while public
region labels follow the new federal state names. Existing active, reserve,
manual and protected ZIP assignments are not renumbered or moved.

Katonga Highland State and Albertine Rift State each have 40 reserve ZIP codes
for authorized admin assignment; other regions retain their existing reserve
capacity.

Existing Entebbe ZIP codes 21401-21405 remain permanently preserved.
The expanded 21406-21420 capacity provides substantially more Lake Victoria
island/locality coverage while retaining the common 21 prefix.
"""

def _codes(prefix:str,count:int):return [f"{prefix}4{i:02d}" for i in range(1,count+1)]
def _reserve(prefix:str,active_count:int,reserve_count:int=20):return [f"{prefix}4{i:02d}" for i in range(active_count+1,active_count+reserve_count+1)]
def _region(name,prefix,active_count,allocation,reserve_count=20):
 return {"name":name,"prefix":prefix,"zip_codes":_codes(prefix,active_count),"reserve_zip_codes":_reserve(prefix,active_count,reserve_count),"allocation":allocation}
DENSE_REGIONS={"JIN","MBA","MBL","GUL"};STANDARD_REGIONS={"ARU","SOR","MOR","HOI","MSK"}
REGIONS={
 "KLA":_region("Kampala Central State","20",50,"metropolitan"),
 "JIN":_region("Nile Source State","22",40,"dense"),
 "MBA":_region("Katonga Highland State","23",40,"dense",40),
 "MBL":_region("Elgon Karamoja State","24",40,"dense"),
 "GUL":_region("Aswa Savannah State","25",40,"dense"),
 "ARU":_region("West Nile State","26",30,"standard"),
 "SOR":_region("Kyoga Kwania State","27",30,"standard"),
 "MOR":_region("Karamoja State","28",30,"standard"),
 "HOI":_region("Albertine Rift State","29",30,"standard",40),
 "MSK":_region("Victoria Equatorial State","30",30,"standard"),
 "ENT":_region("Entebbe & Lake Victoria Islands","21",20,"islands"),
}
ENTEBBE_ZONES={"21401":"Entebbe Central","21402":"Lake Victoria / Entebbe West","21403":"Airport","21404":"Katabi","21405":"Kigungu"}
ENTEBBE_BOUNDS={"min_lat":0.001935,"max_lat":0.1500518,"min_lon":32.3999878,"max_lon":32.5500370}
def all_zip_codes(include_reserve:bool=False):
 values=[]
 for region in REGIONS.values():
  values.extend(region["zip_codes"])
  if include_reserve:values.extend(region.get("reserve_zip_codes",[]))
 return values
def region_for_zip(zip_code:str,include_reserve:bool=True):
 value=str(zip_code).strip()
 for code,region in REGIONS.items():
  if value in region["zip_codes"] or (include_reserve and value in region.get("reserve_zip_codes",[])):return {"code":code,**region}
 return None
def valid_zip(zip_code:str,include_reserve:bool=True)->bool:return region_for_zip(zip_code,include_reserve=include_reserve) is not None
def entebbe_zip_for_coordinates(latitude:float,longitude:float,require_bounds:bool=True):
 lat=float(latitude);lon=float(longitude)
 if require_bounds:
  b=ENTEBBE_BOUNDS
  if not(b["min_lat"]<=lat<=b["max_lat"] and b["min_lon"]<=lon<=b["max_lon"]):return None
 if lon<=32.445000:return "21402"
 if lon<=32.460001:
  if lat<=0.103221:return "21404"
  return "21403"
 if lat<=0.044999:return "21405"
 if lon<=32.500006 and lat<=0.090002:return "21401"
 return "21403"
def entebbe_zone_for_coordinates(latitude:float,longitude:float):
 zip_code=entebbe_zip_for_coordinates(latitude,longitude)
 if not zip_code:return None
 return {"zip_code":zip_code,"name":ENTEBBE_ZONES[zip_code],"region":"ENT"}
