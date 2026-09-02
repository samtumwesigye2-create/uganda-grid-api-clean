import math
import os
import sqlite3
import time
import uuid
from collections import defaultdict

from fastapi import APIRouter, Header, Query

from auth import require_permission

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
router = APIRouter(prefix="/analytics", tags=["analytics"])


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def table_exists(c, name):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def init_db():
    c = conn()
    c.execute("""
      CREATE TABLE IF NOT EXISTS analytics_runs (
        id TEXT PRIMARY KEY,
        model TEXT NOT NULL,
        window_days INTEGER NOT NULL,
        signals INTEGER NOT NULL,
        anomalies INTEGER NOT NULL,
        created_at REAL NOT NULL
      )
    """)
    c.commit(); c.close()


init_db()


def access(code):
    require_permission(code, "shipments:read")


def day_key(ts):
    return time.strftime("%Y-%m-%d", time.localtime(float(ts)))


def order_series(c, window_days):
    now = time.time(); start = now - window_days * 86400
    counts = defaultdict(float); values = defaultdict(float)
    if table_exists(c, "orders"):
        rows = c.execute("SELECT created_at, subtotal, status FROM orders WHERE created_at>=?", (start,)).fetchall()
        for r in rows:
            if r["status"] == "cancelled":
                continue
            k = day_key(r["created_at"]); counts[k] += 1; values[k] += float(r["subtotal"] or 0)
    out=[]
    for i in range(window_days):
        ts = start + i*86400
        k = day_key(ts)
        out.append({"date":k,"orders":counts[k],"value":values[k]})
    return out


def forecast_values(series, days):
    ys=[float(x["orders"]) for x in series]
    n=len(ys)
    if not ys:
        return []
    recent=ys[-min(7,n):]
    avg=sum(recent)/len(recent)
    trend=0.0
    if n>=2:
        xbar=(n-1)/2
        ybar=sum(ys)/n
        denom=sum((i-xbar)**2 for i in range(n)) or 1
        trend=sum((i-xbar)*(y-ybar) for i,y in enumerate(ys))/denom
    base_ts=time.time()
    result=[]
    for i in range(1,days+1):
        predicted=max(0.0, avg + trend*i)
        result.append({"date":day_key(base_ts+i*86400),"predicted_orders":round(predicted,2)})
    mean=sum(ys)/n
    variance=sum((y-mean)**2 for y in ys)/max(1,n-1)
    stdev=math.sqrt(variance)
    confidence=max(0.35,min(0.95,1-(stdev/(mean+1))*0.35))
    return result, round(confidence,3), round(trend,3), round(avg,3)


def anomalies(c):
    out=[]
    if table_exists(c,"products") and table_exists(c,"stock"):
        rows=c.execute("""SELECT p.sku,p.name,p.reorder_point,COALESCE(SUM(s.quantity_on_hand),0) qty
                          FROM products p LEFT JOIN stock s ON s.product_sku=p.sku GROUP BY p.sku""").fetchall()
        for r in rows:
            qty=float(r["qty"] or 0); rp=float(r["reorder_point"] or 0)
            if qty <= rp:
                out.append({"type":"inventory","severity":"high" if qty<=0 else "medium","entity":r["sku"],"message":f"{r['name']} stock {qty:g} is at/below reorder point {rp:g}"})
    if table_exists(c,"orders"):
        cutoff=time.time()-48*3600
        rows=c.execute("SELECT order_number,status,created_at FROM orders WHERE created_at<? AND status NOT IN ('shipped','delivered','cancelled','returned')",(cutoff,)).fetchall()
        for r in rows:
            out.append({"type":"order_delay","severity":"medium","entity":r["order_number"],"message":f"Order remains {r['status']} after 48+ hours"})
    if table_exists(c,"shipments"):
        cutoff=time.time()-72*3600
        rows=c.execute("SELECT shipment_number,delivery_status,status,created_at FROM shipments WHERE created_at<?",(cutoff,)).fetchall()
        for r in rows:
            ds=(r["delivery_status"] or "").lower()
            if ds not in {"delivered","returned","cancelled"}:
                out.append({"type":"shipment_delay","severity":"high","entity":r["shipment_number"],"message":f"Shipment is {ds or r['status']} after 72+ hours"})
    if table_exists(c,"yard_units"):
        cutoff=time.time()-24*3600
        rows=c.execute("SELECT unit_number,status,checked_in_at,created_at FROM yard_units WHERE status NOT IN ('departed','cancelled')").fetchall()
        for r in rows:
            anchor=r["checked_in_at"] or r["created_at"]
            if anchor and anchor<cutoff:
                out.append({"type":"yard_dwell","severity":"medium","entity":r["unit_number"],"message":f"Yard unit remains {r['status']} for 24+ hours"})
    return out


@router.get("/summary")
def summary(window_days: int = Query(default=30, ge=7, le=180), x_access_code: str = Header(default="")):
    access(x_access_code)
    c=conn(); series=order_series(c,window_days); fc,conf,trend,avg=forecast_values(series,7); an=anomalies(c)
    active_orders=0; shipments=0; low_stock=sum(1 for x in an if x["type"]=="inventory")
    if table_exists(c,"orders"):
        active_orders=c.execute("SELECT COUNT(*) n FROM orders WHERE status NOT IN ('delivered','cancelled','returned')").fetchone()["n"]
    if table_exists(c,"shipments"):
        shipments=c.execute("SELECT COUNT(*) n FROM shipments").fetchone()["n"]
    c.close()
    return {"window_days":window_days,"active_orders":active_orders,"shipments":shipments,"signals":len(series)+shipments+active_orders,"anomalies":len(an),"low_stock":low_stock,"forecast_confidence":conf,"daily_order_average":avg,"trend_per_day":trend,"forecast_next_7_days":fc}


@router.get("/forecast")
def forecast(days: int = Query(default=7, ge=1, le=30), window_days: int = Query(default=30, ge=7, le=180), x_access_code: str = Header(default="")):
    access(x_access_code)
    c=conn(); series=order_series(c,window_days); c.close(); fc,conf,trend,avg=forecast_values(series,days)
    return {"model":"moving-average-plus-linear-trend","trained_ml":False,"window_days":window_days,"forecast_days":days,"confidence":conf,"trend_per_day":trend,"daily_order_average":avg,"history":series,"forecast":fc}


@router.get("/anomalies")
def anomaly_list(x_access_code: str = Header(default="")):
    access(x_access_code)
    c=conn(); rows=anomalies(c); c.close()
    return {"count":len(rows),"results":rows}


@router.post("/run")
def run_analysis(window_days: int = Query(default=30, ge=7, le=180), x_access_code: str = Header(default="")):
    access(x_access_code)
    c=conn(); series=order_series(c,window_days); fc,conf,trend,avg=forecast_values(series,7); an=anomalies(c)
    rid="ANL-"+uuid.uuid4().hex[:10].upper(); signals=len(series)
    c.execute("INSERT INTO analytics_runs (id,model,window_days,signals,anomalies,created_at) VALUES (?,?,?,?,?,?)",(rid,"moving-average-plus-linear-trend",window_days,signals,len(an),time.time()))
    c.commit(); c.close()
    return {"run_id":rid,"model":"moving-average-plus-linear-trend","trained_ml":False,"signals":signals,"anomalies":len(an),"confidence":conf,"trend_per_day":trend,"daily_order_average":avg,"forecast":fc,"results":an}


@router.get("/runs")
def list_runs(limit: int = Query(default=50, ge=1, le=200), x_access_code: str = Header(default="")):
    access(x_access_code)
    c=conn(); rows=c.execute("SELECT * FROM analytics_runs ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall(); c.close()
    return {"count":len(rows),"results":[dict(r) for r in rows]}
