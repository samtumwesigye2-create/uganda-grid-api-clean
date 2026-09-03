/* UGATU — role-based U-Code authorization
 * Deny-by-default. Admin is the only wildcard role.
 */
const UGATU_ROLES = Object.freeze({
  administrator: ['*'],
  zipper_admin: ['MAP','ZIP','RPT05'],
  warehouse_manager: ['WHS','INV','PUR','VEN','RPT03','RPT04'],
  warehouse_staff: ['WHS03','WHS05','WHS09','WHS10','WHS11','WHS12','WHS13','WHS14','INV03','INV05','INV09','INV10'],
  shipping_manager: ['SHP','CUS','DRV','FLT','BOL','REC','RPT02'],
  shipping_staff: ['SHP01','SHP02','SHP03','SHP05','SHP07','SHP09','SHP10','SHP11','SHP12','CUS03','CUS05','BOL03','BOL10','REC03','REC10'],
  finance: ['BIL','REC','PUR03','PUR05','PUR06','VEN03','VEN05','RPT06'],
  fleet_manager: ['DRV','FLT','SHP03','SHP05','SHP07','SHP09','SHP10','RPT02'],
  security_admin: ['USR','SEC','ADM03','ADM09','SYS02','SYS03','SYS05','SYS09','RPT07'],
  auditor: ['MAP03','ZIP03','ZIP05','ZIP09','SHP03','SHP05','SHP09','WHS03','WHS05','WHS09','INV03','INV05','INV09','PUR03','PUR05','VEN03','VEN05','VEN09','CUS03','CUS05','CUS09','BIL03','BIL05','BOL03','REC03','REC05','DRV03','DRV09','FLT03','USR03','USR05','USR09','SEC01','SEC03','SEC09','ADM03','ADM05','ADM09','ADM10','RPT','SYS02','SYS03','SYS05','SYS09']
});

function normalizeUGATURole(role) {
  return String(role || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function ugatuRoleRules(role) {
  return UGATU_ROLES[normalizeUGATURole(role)] || [];
}

function ugatuRuleMatches(rule, code) {
  if (rule === '*') return true;
  if (rule === code) return true;
  // A three-letter module rule such as WHS authorizes the whole WHS family.
  return /^[A-Z]{3}$/.test(rule) && code.startsWith(rule);
}

function ugatuCanExecute(role, value) {
  const code = String(value || '').trim().toUpperCase();
  if (!/^[A-Z]{3}\d{2}$/.test(code)) return false;
  return ugatuRoleRules(role).some(rule => ugatuRuleMatches(rule, code));
}

function ugatuAuthorize(role, value) {
  const code = String(value || '').trim().toUpperCase();
  if (!ugatuCanExecute(role, code)) {
    return {ok:false, code, role:normalizeUGATURole(role), error:`Not authorized for UGATU transaction ${code}`};
  }
  return {ok:true, code, role:normalizeUGATURole(role)};
}

function ugatuAllowedCodes(role, registry) {
  const source = registry || (typeof window !== 'undefined' && window.UGATU && window.UGATU.registry) || {};
  return Object.keys(source).filter(code => ugatuCanExecute(role, code));
}

if (typeof module !== 'undefined') module.exports = {UGATU_ROLES, normalizeUGATURole, ugatuRoleRules, ugatuCanExecute, ugatuAuthorize, ugatuAllowedCodes};
if (typeof window !== 'undefined') window.UGATURoles = {roles:UGATU_ROLES, normalizeUGATURole, ugatuRoleRules, ugatuCanExecute, ugatuAuthorize, ugatuAllowedCodes};
