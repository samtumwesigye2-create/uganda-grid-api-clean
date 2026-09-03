"""UGATU — Uganda National Grid Transaction U-Code authorization.
Server-side role enforcement. Deny by default; administrator is the only wildcard role.
"""
import re

ROLE_RULES={
 'administrator':['*'],
 'zipper_admin':['MAP','ZIP','RPT05'],
 'warehouse_manager':['WHS','INV','PUR','VEN','RPT03','RPT04'],
 'warehouse_staff':['WHS03','WHS05','WHS09','WHS10','WHS11','WHS12','WHS13','WHS14','INV03','INV05','INV09','INV10'],
 'shipping_manager':['SHP','CUS','DRV','FLT','BOL','REC','RPT02'],
 'shipping_staff':['SHP01','SHP02','SHP03','SHP05','SHP07','SHP09','SHP10','SHP11','SHP12','CUS03','CUS05','BOL03','BOL10','REC03','REC10'],
 'finance':['BIL','REC','PUR03','PUR05','PUR06','VEN03','VEN05','RPT06'],
 'fleet_manager':['DRV','FLT','SHP03','SHP05','SHP07','SHP09','SHP10','RPT02'],
 'security_admin':['USR','SEC','ADM03','ADM09','SYS02','SYS03','SYS05','SYS09','RPT07'],
 'auditor':['MAP03','ZIP03','ZIP05','ZIP09','SHP03','SHP05','SHP09','WHS03','WHS05','WHS09','INV03','INV05','INV09','PUR03','PUR05','VEN03','VEN05','VEN09','CUS03','CUS05','CUS09','BIL03','BIL05','BOL03','REC03','REC05','DRV03','DRV09','FLT03','USR03','USR05','USR09','SEC01','SEC03','SEC09','ADM03','ADM05','ADM09','ADM10','RPT','SYS02','SYS03','SYS05','SYS09']
}

def normalize_role(role):return re.sub(r'[\s-]+','_',str(role or '').strip().lower())
def normalize_code(code):return str(code or '').strip().upper()
def valid_code(code):return bool(re.fullmatch(r'[A-Z]{3}\d{2}',normalize_code(code)))
def rule_matches(rule,code):return rule=='*' or rule==code or (bool(re.fullmatch(r'[A-Z]{3}',rule)) and code.startswith(rule))
def can_execute(role,code):
 code=normalize_code(code)
 if not valid_code(code):return False
 return any(rule_matches(rule,code) for rule in ROLE_RULES.get(normalize_role(role),[]))
def allowed_codes(role,codes):return [normalize_code(c) for c in codes if can_execute(role,c)]
