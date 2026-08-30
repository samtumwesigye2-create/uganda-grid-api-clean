"""
invoicing.py — Invoice and Bill of Lading generation.

Both documents are generated from an existing shipment record. Printable
views stay public by document number (so they can be shared/printed
without needing a passcode, like a receipt link) — but creating, editing,
voiding/deleting, and viewing the admin list are all permission-gated via
auth.py (invoicing:read / invoicing:write / invoicing:delete).
"""

import os
import sqlite3
import time
import uuid
from fastapi import APIRouter, Form, Header, HTTPException
from fastapi.responses import HTMLResponse

from auth import require_permission

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")

router = APIRouter()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            invoice_number TEXT UNIQUE NOT NULL,
            shipment_number TEXT NOT NULL,
            bill_to_name TEXT NOT NULL,
            bill_to_address TEXT NOT NULL,
            subtotal_ugx REAL NOT NULL,
            tax_ugx REAL NOT NULL,
            total_ugx REAL NOT NULL,
            status TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bills_of_lading (
            id TEXT PRIMARY KEY,
            bol_number TEXT UNIQUE NOT NULL,
            shipment_number TEXT NOT NULL,
            shipper_name TEXT NOT NULL,
            shipper_address TEXT NOT NULL,
            consignee_name TEXT NOT NULL,
            consignee_address TEXT NOT NULL,
            carrier TEXT NOT NULL,
            goods_description TEXT NOT NULL,
            quantity TEXT NOT NULL,
            weight_kg REAL NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS document_counters (
            doc_type TEXT PRIMARY KEY,
            next_number INTEGER NOT NULL
        )
        """
    )
    conn.execute("INSERT OR IGNORE INTO document_counters (doc_type, next_number) VALUES ('invoice', 1)")
    conn.execute("INSERT OR IGNORE INTO document_counters (doc_type, next_number) VALUES ('bol', 1)")
    conn.commit()
    conn.close()


init_db()


def next_document_number(doc_type: str, prefix: str) -> str:
    conn = get_conn()
    n = conn.execute(
        "SELECT next_number FROM document_counters WHERE doc_type = ?", (doc_type,)
    ).fetchone()["next_number"]
    conn.execute(
        "UPDATE document_counters SET next_number = ? WHERE doc_type = ?", (n + 1, doc_type)
    )
    conn.commit()
    conn.close()
    return f"{prefix}-{n:06d}"


def get_shipment(shipment_number: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM shipments WHERE shipment_number = ?", (shipment_number,)
    ).fetchone()
    conn.close()
    return row


DOC_STYLE = """
body { font-family: -apple-system, sans-serif; max-width:600px; margin:30px auto; padding:20px; color:#111; }
h1 { font-size:20px; border-bottom:2px solid #111; padding-bottom:10px; }
table { width:100%; border-collapse:collapse; margin-top:16px; }
td { padding:6px 0; border-bottom:1px solid #eee; vertical-align:top; }
td:first-child { color:#666; width:40%; }
.total { font-size:18px; font-weight:bold; margin-top:16px; }
button { margin-top:20px; padding:10px 16px; border:none; border-radius:6px; background:#e2593a; color:#fff; font-size:15px; }
"""


# --- Invoices ---

@router.post("/invoices/create")
def create_invoice(
    shipment_number: str = Form(...),
    bill_to_name: str = Form(...),
    bill_to_address: str = Form(...),
    tax_rate_percent: float = Form(0),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "invoicing:write")
    shipment = get_shipment(shipment_number)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    subtotal = shipment["rate_ugx"]
    tax = round(subtotal * (tax_rate_percent / 100), 0)
    total = subtotal + tax

    invoice_id = str(uuid.uuid4())
    invoice_number = next_document_number("invoice", "INV")

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO invoices
        (id, invoice_number, shipment_number, bill_to_name, bill_to_address,
         subtotal_ugx, tax_ugx, total_ugx, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (invoice_id, invoice_number, shipment_number, bill_to_name, bill_to_address,
         subtotal, tax, total, "unpaid", time.time()),
    )
    conn.commit()
    conn.close()

    return {
        "invoice_number": invoice_number,
        "shipment_number": shipment_number,
        "subtotal_ugx": subtotal,
        "tax_ugx": tax,
        "total_ugx": total,
        "status": "unpaid",
        "printable_url": f"/invoices/{invoice_number}",
    }


@router.get("/invoices")
def list_invoices(x_access_code: str = Header(default="")):
    require_permission(x_access_code, "invoicing:read")
    conn = get_conn()
    rows = conn.execute("SELECT * FROM invoices ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.get("/invoices/{invoice_number}", response_class=HTMLResponse)
def print_invoice(invoice_number: str):
    conn = get_conn()
    invoice = conn.execute(
        "SELECT * FROM invoices WHERE invoice_number = ?", (invoice_number,)
    ).fetchone()
    conn.close()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    shipment = get_shipment(invoice["shipment_number"])
    date_str = time.strftime("%Y-%m-%d", time.localtime(invoice["created_at"]))

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Invoice — {invoice['invoice_number']}</title>
        <style>{DOC_STYLE}</style>
    </head>
    <body>
        <h1>Uganda National Grid — Invoice</h1>
        <p>Invoice #: <strong>{invoice['invoice_number']}</strong><br>Date: {date_str}</p>
        <table>
            <tr><td>Bill To</td><td>{invoice['bill_to_name']}<br>{invoice['bill_to_address']}</td></tr>
            <tr><td>Shipment #</td><td>{invoice['shipment_number']}</td></tr>
            <tr><td>Route</td><td>{shipment['pickup'] if shipment else '—'} → {shipment['delivery'] if shipment else '—'}</td></tr>
            <tr><td>Weight</td><td>{shipment['weight_kg'] if shipment else '—'} kg</td></tr>
            <tr><td>Subtotal</td><td>UGX {invoice['subtotal_ugx']:,.0f}</td></tr>
            <tr><td>Tax</td><td>UGX {invoice['tax_ugx']:,.0f}</td></tr>
        </table>
        <div class="total">Total Due: UGX {invoice['total_ugx']:,.0f}</div>
        <p>Status: {invoice['status'].upper()}</p>
        <button onclick="window.print()">Print Invoice</button>
    </body>
    </html>
    """


@router.put("/invoices/{invoice_number}")
def update_invoice(
    invoice_number: str,
    bill_to_name: str = Form(None),
    bill_to_address: str = Form(None),
    status: str = Form(None),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "invoicing:write")
    if status is not None and status not in {"unpaid", "paid", "void"}:
        raise HTTPException(status_code=400, detail="status must be unpaid, paid, or void")

    conn = get_conn()
    invoice = conn.execute("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_number,)).fetchone()
    if not invoice:
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found")

    new_name = bill_to_name if bill_to_name is not None else invoice["bill_to_name"]
    new_address = bill_to_address if bill_to_address is not None else invoice["bill_to_address"]
    new_status = status if status is not None else invoice["status"]

    conn.execute(
        "UPDATE invoices SET bill_to_name = ?, bill_to_address = ?, status = ? WHERE invoice_number = ?",
        (new_name, new_address, new_status, invoice_number),
    )
    conn.commit()
    conn.close()
    return {"invoice_number": invoice_number, "bill_to_name": new_name, "bill_to_address": new_address, "status": new_status}


@router.delete("/invoices/{invoice_number}")
def delete_invoice(invoice_number: str, x_access_code: str = Header(default="")):
    require_permission(x_access_code, "invoicing:delete")
    conn = get_conn()
    result = conn.execute("DELETE FROM invoices WHERE invoice_number = ?", (invoice_number,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"invoice_number": invoice_number, "deleted": True}


# --- Bills of lading ---

@router.post("/bol/create")
def create_bol(
    shipment_number: str = Form(...),
    shipper_name: str = Form(...),
    shipper_address: str = Form(...),
    consignee_name: str = Form(...),
    consignee_address: str = Form(...),
    carrier: str = Form(...),
    goods_description: str = Form(...),
    quantity: str = Form(...),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "invoicing:write")
    shipment = get_shipment(shipment_number)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    bol_id = str(uuid.uuid4())
    bol_number = next_document_number("bol", "BOL")

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO bills_of_lading
        (id, bol_number, shipment_number, shipper_name, shipper_address,
         consignee_name, consignee_address, carrier, goods_description,
         quantity, weight_kg, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (bol_id, bol_number, shipment_number, shipper_name, shipper_address,
         consignee_name, consignee_address, carrier, goods_description,
         quantity, shipment["weight_kg"], time.time()),
    )
    conn.commit()
    conn.close()

    return {
        "bol_number": bol_number,
        "shipment_number": shipment_number,
        "printable_url": f"/bol/{bol_number}",
    }


@router.get("/bol")
def list_bol(x_access_code: str = Header(default="")):
    require_permission(x_access_code, "invoicing:read")
    conn = get_conn()
    rows = conn.execute("SELECT * FROM bills_of_lading ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.get("/bol/{bol_number}", response_class=HTMLResponse)
def print_bol(bol_number: str):
    conn = get_conn()
    bol = conn.execute(
        "SELECT * FROM bills_of_lading WHERE bol_number = ?", (bol_number,)
    ).fetchone()
    conn.close()
    if not bol:
        raise HTTPException(status_code=404, detail="Bill of lading not found")

    date_str = time.strftime("%Y-%m-%d", time.localtime(bol["created_at"]))

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Bill of Lading — {bol['bol_number']}</title>
        <style>{DOC_STYLE}</style>
    </head>
    <body>
        <h1>Bill of Lading</h1>
        <p>BOL #: <strong>{bol['bol_number']}</strong><br>Date: {date_str}<br>Shipment #: {bol['shipment_number']}</p>
        <table>
            <tr><td>Shipper</td><td>{bol['shipper_name']}<br>{bol['shipper_address']}</td></tr>
            <tr><td>Consignee</td><td>{bol['consignee_name']}<br>{bol['consignee_address']}</td></tr>
            <tr><td>Carrier</td><td>{bol['carrier']}</td></tr>
            <tr><td>Goods Description</td><td>{bol['goods_description']}</td></tr>
            <tr><td>Quantity</td><td>{bol['quantity']}</td></tr>
            <tr><td>Weight</td><td>{bol['weight_kg']} kg</td></tr>
        </table>
        <p style="margin-top:30px;">Received the above goods in good order and condition.</p>
        <table>
            <tr><td>Shipper Signature</td><td>___________________________</td></tr>
            <tr><td>Carrier Signature</td><td>___________________________</td></tr>
        </table>
        <button onclick="window.print()">Print Bill of Lading</button>
    </body>
    </html>
    """


@router.put("/bol/{bol_number}")
def update_bol(
    bol_number: str,
    shipper_name: str = Form(None),
    shipper_address: str = Form(None),
    consignee_name: str = Form(None),
    consignee_address: str = Form(None),
    carrier: str = Form(None),
    goods_description: str = Form(None),
    quantity: str = Form(None),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "invoicing:write")
    conn = get_conn()
    bol = conn.execute("SELECT * FROM bills_of_lading WHERE bol_number = ?", (bol_number,)).fetchone()
    if not bol:
        conn.close()
        raise HTTPException(status_code=404, detail="Bill of lading not found")

    updated = {
        "shipper_name": shipper_name if shipper_name is not None else bol["shipper_name"],
        "shipper_address": shipper_address if shipper_address is not None else bol["shipper_address"],
        "consignee_name": consignee_name if consignee_name is not None else bol["consignee_name"],
        "consignee_address": consignee_address if consignee_address is not None else bol["consignee_address"],
        "carrier": carrier if carrier is not None else bol["carrier"],
        "goods_description": goods_description if goods_description is not None else bol["goods_description"],
        "quantity": quantity if quantity is not None else bol["quantity"],
    }
    conn.execute(
        """
        UPDATE bills_of_lading SET shipper_name=?, shipper_address=?, consignee_name=?,
        consignee_address=?, carrier=?, goods_description=?, quantity=? WHERE bol_number=?
        """,
        (*updated.values(), bol_number),
    )
    conn.commit()
    conn.close()
    return {"bol_number": bol_number, **updated}


@router.delete("/bol/{bol_number}")
def delete_bol(bol_number: str, x_access_code: str = Header(default="")):
    require_permission(x_access_code, "invoicing:delete")
    conn = get_conn()
    result = conn.execute("DELETE FROM bills_of_lading WHERE bol_number = ?", (bol_number,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Bill of lading not found")
    return {"bol_number": bol_number, "deleted": True}


# --- Analytics ---

@router.get("/invoicing/analytics")
def invoicing_analytics(x_access_code: str = Header(default="")):
    require_permission(x_access_code, "invoicing:read")
    conn = get_conn()
    invoices = conn.execute("SELECT * FROM invoices").fetchall()
    conn.close()

    total_invoiced = sum(i["total_ugx"] for i in invoices)
    total_paid = sum(i["total_ugx"] for i in invoices if i["status"] == "paid")
    total_outstanding = sum(i["total_ugx"] for i in invoices if i["status"] == "unpaid")

    return {
        "invoice_count": len(invoices),
        "total_invoiced_ugx": total_invoiced,
        "total_paid_ugx": total_paid,
        "total_outstanding_ugx": total_outstanding,
        "unpaid_count": sum(1 for i in invoices if i["status"] == "unpaid"),
        "paid_count": sum(1 for i in invoices if i["status"] == "paid"),
        "void_count": sum(1 for i in invoices if i["status"] == "void"),
    }
