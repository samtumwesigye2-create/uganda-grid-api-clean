"""
inventory.py — Warehouse inventory management.

Architected for multi-warehouse from day one: a `warehouses` table exists
even though only one location runs today. Stock is tracked per
(product, warehouse) pair, so adding a second warehouse later is just
inserting a new row and starting to record stock against it — no schema
changes, no data migration.

Access is permission-gated via auth.py: the master admin passcode always
has full access; staff accounts only get what they've been granted
(inventory:read / inventory:write / inventory:delete).
"""

import os
import sqlite3
import time
import uuid
from fastapi import APIRouter, Form, Header, HTTPException, Query

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
        CREATE TABLE IF NOT EXISTS warehouses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            unit_cost REAL NOT NULL DEFAULT 0,
            reorder_point REAL NOT NULL DEFAULT 0,
            reorder_quantity REAL NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stock (
            product_sku TEXT NOT NULL,
            warehouse_id TEXT NOT NULL,
            quantity_on_hand REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (product_sku, warehouse_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_movements (
            id TEXT PRIMARY KEY,
            product_sku TEXT NOT NULL,
            warehouse_id TEXT NOT NULL,
            movement_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            note TEXT,
            created_at REAL NOT NULL
        )
        """
    )
    existing = conn.execute("SELECT COUNT(*) as c FROM warehouses").fetchone()
    if existing["c"] == 0:
        conn.execute(
            "INSERT INTO warehouses (id, name, address, is_active, created_at) VALUES (?,?,?,?,?)",
            ("main", "Main Warehouse", "", 1, time.time()),
        )
    conn.commit()
    conn.close()


init_db()


def log_movement(conn, product_sku, warehouse_id, movement_type, quantity, note):
    conn.execute(
        """
        INSERT INTO stock_movements (id, product_sku, warehouse_id, movement_type, quantity, note, created_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (str(uuid.uuid4()), product_sku, warehouse_id, movement_type, quantity, note, time.time()),
    )


# --- Warehouses ---

@router.post("/inventory/warehouses")
def create_warehouse(
    name: str = Form(...),
    address: str = Form(""),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "inventory:write")
    warehouse_id = str(uuid.uuid4())[:8]
    conn = get_conn()
    conn.execute(
        "INSERT INTO warehouses (id, name, address, is_active, created_at) VALUES (?,?,?,?,?)",
        (warehouse_id, name, address, 1, time.time()),
    )
    conn.commit()
    conn.close()
    return {"id": warehouse_id, "name": name, "address": address}


@router.get("/inventory/warehouses")
def list_warehouses(x_access_code: str = Header(default="")):
    require_permission(x_access_code, "inventory:read")
    conn = get_conn()
    rows = conn.execute("SELECT * FROM warehouses").fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.put("/inventory/warehouses/{warehouse_id}")
def update_warehouse(
    warehouse_id: str,
    name: str = Form(None),
    address: str = Form(None),
    is_active: bool = Form(None),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "inventory:write")
    conn = get_conn()
    warehouse = conn.execute("SELECT * FROM warehouses WHERE id = ?", (warehouse_id,)).fetchone()
    if not warehouse:
        conn.close()
        raise HTTPException(status_code=404, detail="Warehouse not found")

    new_name = name if name is not None else warehouse["name"]
    new_address = address if address is not None else warehouse["address"]
    new_is_active = int(is_active) if is_active is not None else warehouse["is_active"]

    conn.execute(
        "UPDATE warehouses SET name = ?, address = ?, is_active = ? WHERE id = ?",
        (new_name, new_address, new_is_active, warehouse_id),
    )
    conn.commit()
    conn.close()
    return {"id": warehouse_id, "name": new_name, "address": new_address, "is_active": bool(new_is_active)}


@router.delete("/inventory/warehouses/{warehouse_id}")
def delete_warehouse(warehouse_id: str, x_access_code: str = Header(default="")):
    """Deactivates rather than hard-deletes — a warehouse with stock history
    shouldn't disappear and orphan movement records. Set is_active to 0."""
    require_permission(x_access_code, "inventory:delete")
    if warehouse_id == "main":
        raise HTTPException(status_code=400, detail="Cannot deactivate the default warehouse")
    conn = get_conn()
    result = conn.execute("UPDATE warehouses SET is_active = 0 WHERE id = ?", (warehouse_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return {"id": warehouse_id, "deactivated": True}


# --- Products ---

@router.post("/inventory/products")
def create_product(
    sku: str = Form(...),
    name: str = Form(...),
    unit_cost: float = Form(0),
    reorder_point: float = Form(0),
    reorder_quantity: float = Form(0),
    initial_quantity: float = Form(0),
    warehouse_id: str = Form("main"),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "inventory:write")
    conn = get_conn()
    existing = conn.execute("SELECT sku FROM products WHERE sku = ?", (sku,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="SKU already exists")

    conn.execute(
        """
        INSERT INTO products (sku, name, unit_cost, reorder_point, reorder_quantity, created_at)
        VALUES (?,?,?,?,?,?)
        """,
        (sku, name, unit_cost, reorder_point, reorder_quantity, time.time()),
    )
    conn.execute(
        "INSERT INTO stock (product_sku, warehouse_id, quantity_on_hand) VALUES (?,?,?)",
        (sku, warehouse_id, initial_quantity),
    )
    if initial_quantity:
        log_movement(conn, sku, warehouse_id, "receive", initial_quantity, "Initial stock")
    conn.commit()
    conn.close()
    return {"sku": sku, "name": name, "warehouse_id": warehouse_id, "quantity_on_hand": initial_quantity}


@router.get("/inventory/products")
def list_products(x_access_code: str = Header(default="")):
    require_permission(x_access_code, "inventory:read")
    conn = get_conn()
    products = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    results = []
    for p in products:
        stock_rows = conn.execute(
            "SELECT warehouse_id, quantity_on_hand FROM stock WHERE product_sku = ?", (p["sku"],)
        ).fetchall()
        total_qty = sum(r["quantity_on_hand"] for r in stock_rows)
        results.append({
            **dict(p),
            "total_quantity_on_hand": total_qty,
            "by_warehouse": [dict(r) for r in stock_rows],
        })
    conn.close()
    return {"count": len(results), "results": results}


@router.get("/inventory/products/{sku}")
def get_product(sku: str, x_access_code: str = Header(default="")):
    require_permission(x_access_code, "inventory:read")
    conn = get_conn()
    product = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
    stock_rows = conn.execute(
        "SELECT warehouse_id, quantity_on_hand FROM stock WHERE product_sku = ?", (sku,)
    ).fetchall()
    conn.close()
    total_qty = sum(r["quantity_on_hand"] for r in stock_rows)
    return {
        **dict(product),
        "total_quantity_on_hand": total_qty,
        "by_warehouse": [dict(r) for r in stock_rows],
    }


@router.put("/inventory/products/{sku}")
def update_product(
    sku: str,
    name: str = Form(None),
    unit_cost: float = Form(None),
    reorder_point: float = Form(None),
    reorder_quantity: float = Form(None),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "inventory:write")
    conn = get_conn()
    product = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    new_name = name if name is not None else product["name"]
    new_unit_cost = unit_cost if unit_cost is not None else product["unit_cost"]
    new_reorder_point = reorder_point if reorder_point is not None else product["reorder_point"]
    new_reorder_quantity = reorder_quantity if reorder_quantity is not None else product["reorder_quantity"]

    conn.execute(
        "UPDATE products SET name = ?, unit_cost = ?, reorder_point = ?, reorder_quantity = ? WHERE sku = ?",
        (new_name, new_unit_cost, new_reorder_point, new_reorder_quantity, sku),
    )
    conn.commit()
    conn.close()
    return {
        "sku": sku, "name": new_name, "unit_cost": new_unit_cost,
        "reorder_point": new_reorder_point, "reorder_quantity": new_reorder_quantity,
    }


@router.delete("/inventory/products/{sku}")
def delete_product(sku: str, x_access_code: str = Header(default="")):
    """Hard-deletes the product and its stock rows. Movement history is kept
    for audit purposes even after the product itself is removed."""
    require_permission(x_access_code, "inventory:delete")
    conn = get_conn()
    product = conn.execute("SELECT sku FROM products WHERE sku = ?", (sku,)).fetchone()
    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
    conn.execute("DELETE FROM stock WHERE product_sku = ?", (sku,))
    conn.execute("DELETE FROM products WHERE sku = ?", (sku,))
    conn.commit()
    conn.close()
    return {"sku": sku, "deleted": True}


# --- Stock movements ---

@router.post("/inventory/stock/receive")
def receive_stock(
    sku: str = Form(...),
    quantity: float = Form(..., gt=0),
    warehouse_id: str = Form("main"),
    note: str = Form(""),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "inventory:write")
    conn = get_conn()
    product = conn.execute("SELECT sku FROM products WHERE sku = ?", (sku,)).fetchone()
    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    row = conn.execute(
        "SELECT quantity_on_hand FROM stock WHERE product_sku = ? AND warehouse_id = ?",
        (sku, warehouse_id),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE stock SET quantity_on_hand = quantity_on_hand + ? WHERE product_sku = ? AND warehouse_id = ?",
            (quantity, sku, warehouse_id),
        )
    else:
        conn.execute(
            "INSERT INTO stock (product_sku, warehouse_id, quantity_on_hand) VALUES (?,?,?)",
            (sku, warehouse_id, quantity),
        )
    log_movement(conn, sku, warehouse_id, "receive", quantity, note)
    conn.commit()
    new_qty = conn.execute(
        "SELECT quantity_on_hand FROM stock WHERE product_sku = ? AND warehouse_id = ?",
        (sku, warehouse_id),
    ).fetchone()["quantity_on_hand"]
    conn.close()
    return {"sku": sku, "warehouse_id": warehouse_id, "quantity_on_hand": new_qty}


@router.post("/inventory/stock/dispatch")
def dispatch_stock(
    sku: str = Form(...),
    quantity: float = Form(..., gt=0),
    warehouse_id: str = Form("main"),
    note: str = Form(""),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "inventory:write")
    conn = get_conn()
    row = conn.execute(
        "SELECT quantity_on_hand FROM stock WHERE product_sku = ? AND warehouse_id = ?",
        (sku, warehouse_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="No stock record for this product/warehouse")
    if row["quantity_on_hand"] < quantity:
        conn.close()
        raise HTTPException(status_code=400, detail="Insufficient stock")

    conn.execute(
        "UPDATE stock SET quantity_on_hand = quantity_on_hand - ? WHERE product_sku = ? AND warehouse_id = ?",
        (quantity, sku, warehouse_id),
    )
    log_movement(conn, sku, warehouse_id, "dispatch", quantity, note)
    conn.commit()
    new_qty = conn.execute(
        "SELECT quantity_on_hand FROM stock WHERE product_sku = ? AND warehouse_id = ?",
        (sku, warehouse_id),
    ).fetchone()["quantity_on_hand"]
    conn.close()
    return {"sku": sku, "warehouse_id": warehouse_id, "quantity_on_hand": new_qty}


@router.post("/inventory/stock/adjust")
def adjust_stock(
    sku: str = Form(...),
    new_quantity: float = Form(..., ge=0),
    warehouse_id: str = Form("main"),
    note: str = Form(...),
    x_access_code: str = Header(default=""),
):
    """Manual correction — e.g. after a physical stock count finds a
    discrepancy. Logs the delta as an 'adjustment' movement so the audit
    trail shows exactly what changed and why (note is required)."""
    require_permission(x_access_code, "inventory:write")
    conn = get_conn()
    row = conn.execute(
        "SELECT quantity_on_hand FROM stock WHERE product_sku = ? AND warehouse_id = ?",
        (sku, warehouse_id),
    ).fetchone()
    old_qty = row["quantity_on_hand"] if row else 0
    delta = new_quantity - old_qty

    if row:
        conn.execute(
            "UPDATE stock SET quantity_on_hand = ? WHERE product_sku = ? AND warehouse_id = ?",
            (new_quantity, sku, warehouse_id),
        )
    else:
        conn.execute(
            "INSERT INTO stock (product_sku, warehouse_id, quantity_on_hand) VALUES (?,?,?)",
            (sku, warehouse_id, new_quantity),
        )
    log_movement(conn, sku, warehouse_id, "adjustment", delta, note)
    conn.commit()
    conn.close()
    return {"sku": sku, "warehouse_id": warehouse_id, "old_quantity": old_qty, "new_quantity": new_quantity, "delta": delta}


@router.get("/inventory/movements")
def list_movements(
    sku: str = Query(default=""),
    warehouse_id: str = Query(default=""),
    limit: int = Query(default=100, le=500),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "inventory:read")
    conn = get_conn()
    query = "SELECT * FROM stock_movements WHERE 1=1"
    params = []
    if sku:
        query += " AND product_sku = ?"
        params.append(sku)
    if warehouse_id:
        query += " AND warehouse_id = ?"
        params.append(warehouse_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


# --- Reorder + forecasting + analytics ---

@router.get("/inventory/reorder")
def reorder_needed(x_access_code: str = Header(default="")):
    require_permission(x_access_code, "inventory:read")
    conn = get_conn()
    products = conn.execute("SELECT * FROM products").fetchall()
    flagged = []
    for p in products:
        total_qty = conn.execute(
            "SELECT COALESCE(SUM(quantity_on_hand), 0) as total FROM stock WHERE product_sku = ?",
            (p["sku"],),
        ).fetchone()["total"]
        if total_qty <= p["reorder_point"]:
            flagged.append({
                "sku": p["sku"],
                "name": p["name"],
                "quantity_on_hand": total_qty,
                "reorder_point": p["reorder_point"],
                "suggested_reorder_quantity": p["reorder_quantity"],
            })
    conn.close()
    return {"count": len(flagged), "results": flagged}


@router.get("/inventory/forecast/{sku}")
def forecast_demand(
    sku: str,
    days: int = Query(default=30, ge=1, le=365),
    x_access_code: str = Header(default=""),
):
    require_permission(x_access_code, "inventory:read")
    conn = get_conn()
    product = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    cutoff = time.time() - (days * 86400)
    dispatches = conn.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) as total
        FROM stock_movements
        WHERE product_sku = ? AND movement_type = 'dispatch' AND created_at >= ?
        """,
        (sku, cutoff),
    ).fetchone()["total"]

    total_qty = conn.execute(
        "SELECT COALESCE(SUM(quantity_on_hand), 0) as total FROM stock WHERE product_sku = ?",
        (sku,),
    ).fetchone()["total"]
    conn.close()

    avg_daily_usage = dispatches / days if days else 0
    days_until_stockout = round(total_qty / avg_daily_usage, 1) if avg_daily_usage > 0 else None

    return {
        "sku": sku,
        "lookback_days": days,
        "total_dispatched": dispatches,
        "avg_daily_usage": round(avg_daily_usage, 2),
        "current_quantity_on_hand": total_qty,
        "days_until_stockout": days_until_stockout,
        "at_or_below_reorder_point": total_qty <= product["reorder_point"],
    }


@router.get("/inventory/analytics")
def inventory_analytics(x_access_code: str = Header(default="")):
    """Overview for the admin: total inventory value, movement volume,
    what's trending, what needs attention."""
    require_permission(x_access_code, "inventory:read")
    conn = get_conn()

    products = conn.execute("SELECT * FROM products").fetchall()
    total_value = 0
    total_units = 0
    reorder_count = 0
    for p in products:
        qty = conn.execute(
            "SELECT COALESCE(SUM(quantity_on_hand), 0) as total FROM stock WHERE product_sku = ?",
            (p["sku"],),
        ).fetchone()["total"]
        total_value += qty * p["unit_cost"]
        total_units += qty
        if qty <= p["reorder_point"]:
            reorder_count += 1

    cutoff_30d = time.time() - (30 * 86400)
    top_movers = conn.execute(
        """
        SELECT product_sku, SUM(quantity) as total_dispatched
        FROM stock_movements
        WHERE movement_type = 'dispatch' AND created_at >= ?
        GROUP BY product_sku
        ORDER BY total_dispatched DESC
        LIMIT 5
        """,
        (cutoff_30d,),
    ).fetchall()

    conn.close()
    return {
        "total_products": len(products),
        "total_units_on_hand": total_units,
        "total_inventory_value": round(total_value, 2),
        "products_needing_reorder": reorder_count,
        "top_movers_last_30_days": [dict(r) for r in top_movers],
    }
