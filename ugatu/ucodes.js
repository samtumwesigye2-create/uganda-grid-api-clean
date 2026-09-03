/* UGATU — Uganda National Grid Transaction U-Codes
 * Central transaction registry. U-Codes are stable identifiers; routes can evolve.
 */

const UGATU = Object.freeze({
  MAP01:{name:'Search Address',route:'/app#search',permission:'map.search'},
  MAP02:{name:'Route to Destination',route:'/app#route',permission:'map.route'},
  MAP03:{name:'Display Location',route:'/app#location',permission:'map.view'},
  MAP10:{name:'Report Map Issue',route:'/app#report',permission:'map.report'},

  ZIP01:{name:'Create ZIPPER',route:'/admin#zip-create',permission:'zipper.create'},
  ZIP02:{name:'Change ZIPPER',route:'/admin#zip-edit',permission:'zipper.edit'},
  ZIP03:{name:'Display ZIPPER',route:'/admin#zip-view',permission:'zipper.view'},
  ZIP05:{name:'ZIPPER Search',route:'/admin#zip-search',permission:'zipper.view'},
  ZIP06:{name:'Approve ZIPPER',route:'/admin#zip-approve',permission:'zipper.approve'},
  ZIP07:{name:'Assign ZIPPER',route:'/admin#zip-assign',permission:'zipper.assign'},
  ZIP08:{name:'Reassign ZIPPER',route:'/admin#zip-reassign',permission:'zipper.assign'},
  ZIP09:{name:'ZIPPER History',route:'/admin#zip-history',permission:'zipper.audit'},
  ZIP10:{name:'Generate ZIPPERs',route:'/admin#zip-generate',permission:'zipper.generate'},
  ZIP11:{name:'Population Allocation',route:'/admin#zip-population',permission:'zipper.allocate'},
  ZIP12:{name:'Reserve ZIPPER',route:'/admin#zip-reserve',permission:'zipper.reserve'},
  ZIP13:{name:'Special ZIPPER',route:'/admin#zip-special',permission:'zipper.special'},
  ZIP14:{name:'Grid Coverage Check',route:'/admin#zip-coverage',permission:'zipper.view'},

  SHP01:{name:'Create Shipment',route:'/ship#new',permission:'shipment.create'},
  SHP02:{name:'Change Shipment',route:'/ship#edit',permission:'shipment.edit'},
  SHP03:{name:'Display Shipment',route:'/ship#view',permission:'shipment.view'},
  SHP04:{name:'Cancel Shipment',route:'/ship#cancel',permission:'shipment.cancel'},
  SHP05:{name:'Shipment List',route:'/ship#list',permission:'shipment.view'},
  SHP06:{name:'Release Shipment',route:'/ship#release',permission:'shipment.release'},
  SHP07:{name:'Assign Shipment',route:'/ship#assign',permission:'shipment.assign'},
  SHP08:{name:'Transfer Shipment',route:'/ship#transfer',permission:'shipment.transfer'},
  SHP09:{name:'Shipment History',route:'/ship#history',permission:'shipment.audit'},
  SHP10:{name:'Track Shipment',route:'/ship#track',permission:'shipment.track'},
  SHP11:{name:'Dispatch Shipment',route:'/ship#dispatch',permission:'shipment.dispatch'},
  SHP12:{name:'Confirm Delivery',route:'/ship#delivery',permission:'shipment.deliver'},

  WHS01:{name:'Create Warehouse Item',route:'/warehouse#item-new',permission:'warehouse.create'},
  WHS02:{name:'Change Warehouse Item',route:'/warehouse#item-edit',permission:'warehouse.edit'},
  WHS03:{name:'Display Item',route:'/warehouse#item-view',permission:'warehouse.view'},
  WHS05:{name:'Inventory List',route:'/warehouse#inventory',permission:'warehouse.view'},
  WHS07:{name:'Assign Storage Location',route:'/warehouse#location',permission:'warehouse.assign'},
  WHS08:{name:'Stock Transfer',route:'/warehouse#transfer',permission:'warehouse.transfer'},
  WHS09:{name:'Movement History',route:'/warehouse#history',permission:'warehouse.audit'},
  WHS10:{name:'Goods Receipt',route:'/warehouse#receiving',permission:'warehouse.receive'},
  WHS11:{name:'Goods Issue',route:'/warehouse#issue',permission:'warehouse.issue'},
  WHS12:{name:'Pick Order',route:'/warehouse#pick',permission:'warehouse.pick'},
  WHS13:{name:'Pack Order',route:'/warehouse#pack',permission:'warehouse.pack'},
  WHS14:{name:'Dispatch Order',route:'/warehouse#dispatch',permission:'warehouse.dispatch'},

  INV01:{name:'Create Inventory Record',route:'/warehouse#inventory-new',permission:'inventory.create'},
  INV02:{name:'Change Inventory',route:'/warehouse#inventory-edit',permission:'inventory.edit'},
  INV03:{name:'Stock Overview',route:'/warehouse#stock',permission:'inventory.view'},
  INV05:{name:'Material / Item List',route:'/warehouse#materials',permission:'inventory.view'},
  INV08:{name:'Transfer Stock',route:'/warehouse#stock-transfer',permission:'inventory.transfer'},
  INV09:{name:'Inventory History',route:'/warehouse#inventory-history',permission:'inventory.audit'},
  INV10:{name:'Physical Count',route:'/warehouse#physical-count',permission:'inventory.count'},
  INV11:{name:'Post Count Difference',route:'/warehouse#count-difference',permission:'inventory.adjust'},

  PUR01:{name:'Create Purchase Order',route:'/warehouse#po-new',permission:'purchasing.create'},
  PUR02:{name:'Change Purchase Order',route:'/warehouse#po-edit',permission:'purchasing.edit'},
  PUR03:{name:'Display Purchase Order',route:'/warehouse#po-view',permission:'purchasing.view'},
  PUR04:{name:'Cancel Purchase Order',route:'/warehouse#po-cancel',permission:'purchasing.cancel'},
  PUR05:{name:'Purchase Order List',route:'/warehouse#po-list',permission:'purchasing.view'},
  PUR06:{name:'Approve Purchase Order',route:'/warehouse#po-approve',permission:'purchasing.approve'},
  PUR10:{name:'Create Purchase Requisition',route:'/warehouse#pr-new',permission:'purchasing.requisition'},
  PUR11:{name:'Create RFQ',route:'/warehouse#rfq-new',permission:'purchasing.rfq'},

  VEN01:{name:'Create Vendor',route:'/warehouse#vendor-new',permission:'vendor.create'},
  VEN02:{name:'Change Vendor',route:'/warehouse#vendor-edit',permission:'vendor.edit'},
  VEN03:{name:'Display Vendor',route:'/warehouse#vendor-view',permission:'vendor.view'},
  VEN05:{name:'Vendor List',route:'/warehouse#vendors',permission:'vendor.view'},
  VEN06:{name:'Approve Vendor',route:'/warehouse#vendor-approve',permission:'vendor.approve'},
  VEN09:{name:'Vendor History',route:'/warehouse#vendor-history',permission:'vendor.audit'},

  CUS01:{name:'Create Customer',route:'/ship#customer-new',permission:'customer.create'},
  CUS02:{name:'Change Customer',route:'/ship#customer-edit',permission:'customer.edit'},
  CUS03:{name:'Display Customer',route:'/ship#customer-view',permission:'customer.view'},
  CUS05:{name:'Customer Search',route:'/ship#customers',permission:'customer.view'},
  CUS09:{name:'Customer History',route:'/ship#customer-history',permission:'customer.audit'},

  BIL01:{name:'Create Invoice',route:'/admin#invoice-new',permission:'billing.create'},
  BIL02:{name:'Change Invoice',route:'/admin#invoice-edit',permission:'billing.edit'},
  BIL03:{name:'Display Invoice',route:'/admin#invoice-view',permission:'billing.view'},
  BIL04:{name:'Void Invoice',route:'/admin#invoice-void',permission:'billing.void'},
  BIL05:{name:'Invoice List',route:'/admin#invoices',permission:'billing.view'},
  BIL06:{name:'Approve Invoice',route:'/admin#invoice-approve',permission:'billing.approve'},
  BIL10:{name:'Generate Invoice PDF',route:'/admin#invoice-pdf',permission:'billing.export'},

  BOL01:{name:'Create Bill of Lading',route:'/admin#bol-new',permission:'bol.create'},
  BOL02:{name:'Change Bill of Lading',route:'/admin#bol-edit',permission:'bol.edit'},
  BOL03:{name:'Display Bill of Lading',route:'/admin#bol-view',permission:'bol.view'},
  BOL06:{name:'Release Bill of Lading',route:'/admin#bol-release',permission:'bol.release'},
  BOL10:{name:'Print / Export Bill of Lading',route:'/admin#bol-export',permission:'bol.export'},

  REC01:{name:'Create Receipt',route:'/admin#receipt-new',permission:'receipt.create'},
  REC03:{name:'Display Receipt',route:'/admin#receipt-view',permission:'receipt.view'},
  REC04:{name:'Void Receipt',route:'/admin#receipt-void',permission:'receipt.void'},
  REC05:{name:'Receipt List',route:'/admin#receipts',permission:'receipt.view'},
  REC10:{name:'Print Receipt',route:'/admin#receipt-print',permission:'receipt.export'},

  DRV01:{name:'Create Driver',route:'/ship#driver-new',permission:'driver.create'},
  DRV02:{name:'Change Driver',route:'/ship#driver-edit',permission:'driver.edit'},
  DRV03:{name:'Display Driver',route:'/ship#driver-view',permission:'driver.view'},
  DRV07:{name:'Assign Driver',route:'/ship#driver-assign',permission:'driver.assign'},
  DRV09:{name:'Driver History',route:'/ship#driver-history',permission:'driver.audit'},
  FLT01:{name:'Register Vehicle',route:'/ship#vehicle-new',permission:'fleet.create'},
  FLT03:{name:'Display Vehicle',route:'/ship#vehicle-view',permission:'fleet.view'},
  FLT07:{name:'Assign Vehicle',route:'/ship#vehicle-assign',permission:'fleet.assign'},
  FLT10:{name:'Vehicle Tracking',route:'/ship#vehicle-track',permission:'fleet.track'},

  USR01:{name:'Create User',route:'/admin#user-new',permission:'user.create'},
  USR02:{name:'Change User',route:'/admin#user-edit',permission:'user.edit'},
  USR03:{name:'Display User',route:'/admin#user-view',permission:'user.view'},
  USR04:{name:'Disable User',route:'/admin#user-disable',permission:'user.disable'},
  USR05:{name:'User List',route:'/admin#users',permission:'user.view'},
  USR07:{name:'Assign Role',route:'/admin#roles',permission:'user.role'},
  USR09:{name:'User Audit',route:'/admin#user-audit',permission:'user.audit'},
  SEC01:{name:'Security Dashboard',route:'/admin#security',permission:'security.view'},
  SEC02:{name:'MFA Management',route:'/admin#mfa',permission:'security.mfa'},
  SEC03:{name:'Sessions',route:'/admin#sessions',permission:'security.sessions'},
  SEC04:{name:'Revoke Session',route:'/admin#session-revoke',permission:'security.revoke'},
  SEC09:{name:'Security Audit',route:'/admin#security-audit',permission:'security.audit'},

  ADM01:{name:'Admin Dashboard',route:'/admin',permission:'admin.view'},
  ADM02:{name:'System Configuration',route:'/admin#configuration',permission:'admin.configure'},
  ADM03:{name:'System Status',route:'/admin#status',permission:'admin.view'},
  ADM05:{name:'Service List',route:'/admin#services',permission:'admin.view'},
  ADM06:{name:'Approval Queue',route:'/admin#approvals',permission:'admin.approve'},
  ADM09:{name:'System Audit Log',route:'/admin#audit',permission:'admin.audit'},
  ADM10:{name:'Database Status',route:'/admin#database',permission:'admin.database'},

  RPT01:{name:'Operations Dashboard',route:'/admin#reports-operations',permission:'reports.operations'},
  RPT02:{name:'Shipment Report',route:'/admin#reports-shipments',permission:'reports.shipments'},
  RPT03:{name:'Inventory Report',route:'/admin#reports-inventory',permission:'reports.inventory'},
  RPT04:{name:'Warehouse Report',route:'/admin#reports-warehouse',permission:'reports.warehouse'},
  RPT05:{name:'ZIPPER Report',route:'/admin#reports-zipper',permission:'reports.zipper'},
  RPT06:{name:'Financial Report',route:'/admin#reports-finance',permission:'reports.finance'},
  RPT07:{name:'User Activity Report',route:'/admin#reports-users',permission:'reports.users'},
  RPT08:{name:'Performance Report',route:'/admin#reports-performance',permission:'reports.performance'},

  SYS01:{name:'System Home',route:'/admin#system',permission:'system.view'},
  SYS02:{name:'Health Check',route:'/admin#health',permission:'system.health'},
  SYS03:{name:'Service Status',route:'/admin#service-status',permission:'system.view'},
  SYS04:{name:'Maintenance',route:'/admin#maintenance',permission:'system.maintenance'},
  SYS05:{name:'Job Monitor',route:'/admin#jobs',permission:'system.jobs'},
  SYS06:{name:'Release Management',route:'/admin#releases',permission:'system.release'},
  SYS09:{name:'System Logs',route:'/admin#logs',permission:'system.logs'}
});

function normalizeUCode(value){ return String(value || '').trim().toUpperCase(); }
function getUGATUTransaction(value){ return UGATU[normalizeUCode(value)] || null; }
function searchUGATU(value){
  const q = normalizeUCode(value);
  return Object.entries(UGATU)
    .filter(([code, tx]) => code.includes(q) || tx.name.toUpperCase().includes(q))
    .map(([code, tx]) => ({code, ...tx}));
}
function executeUGATU(value, permissions){
  const code = normalizeUCode(value);
  const tx = UGATU[code];
  if (!tx) return {ok:false, code, error:`Unknown UGATU transaction ${code}`};
  if (Array.isArray(permissions) && !permissions.includes('*') && !permissions.includes(tx.permission)) {
    return {ok:false, code, error:`Not authorized for transaction ${code}`};
  }
  return {ok:true, code, ...tx};
}

if (typeof module !== 'undefined') module.exports = {UGATU, normalizeUCode, getUGATUTransaction, searchUGATU, executeUGATU};
if (typeof window !== 'undefined') window.UGATU = {registry:UGATU, normalizeUCode, getUGATUTransaction, searchUGATU, executeUGATU};
