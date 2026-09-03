from __future__ import annotations

import math
import os
import sqlite3
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from ugamap_core import core_address, core_reports, core_route

router = APIRouter(prefix="/api/ugatu/driver-routing", tags=["UGATU Driver Routing"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
FINAL = {"completed", "failed", "cancelled", "dropped_off_customer", "dropped_off_warehouse"}
IN_PROGRESS = {"en_route_pickup", "arrived_pickup", "picked_up", "en_route_dropoff", "arrived_dropoff"}
_ROUTE_CACHE: dict[tuple[float, float, float, float], tuple[float, dict[str, Any]]] = {}
CACHE_TTL_S = 90
MAX_ROUTED_STOPS = 12
INCIDENT_CORRIDOR_M = 350
# Safety/road-operability reports influence sequencing. Police reports are deliberately informational only.
INCIDENT_DELAY_S = {
    "road_closure": 1200,
    "accident": 600,
    "traffic": 480,
    "bridge": 720,
    "weather": 360,
    "road_hazard": 420,
}


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _driver(passcode: str) -> dict[str, Any]:
    if not passcode:
        raise HTTPException(401, "Driver passcode required")
    c = _conn()
    try:
        row = c.execute("SELECT * FROM drivers WHERE passcode=? AND is_active=1", (passcode,)).fetchone()
    finally:
        c.close()
    if not row:
        raise HTTPException(401, "Invalid driver passcode")
    return dict(row)


def _leg_mode(task: dict[str, Any]) -> str:
    status = str(task.get("status") or "").lower()
    ttype = str(task.get("task_type") or "").lower()
    notes = str(task.get("notes") or "").lower()
    pickup_only = "pickup_only" in ttype or "[pickup_only]" in notes
    if "warehouse_transfer" in ttype or "handoff" in ttype:
        return "HANDOFF"
    if "pickup" in ttype and status in {"picked_up", "en_route_dropoff", "arrived_dropoff"} and not pickup_only:
        return "DELIVERY"
    if "pickup" in ttype:
        return "PICKUP"
    return "DELIVERY"


def _delivery(c, shipment_number: str | None) -> dict[str, str]:
    if not shipment_number:
        return {}
    try:
        row = c.execute(
            "SELECT delivery_address,delivery_grid_id FROM orders WHERE shipment_number=? ORDER BY updated_at DESC LIMIT 1",
            (shipment_number,),
        ).fetchone()
        if row:
            return {"delivery_address": row["delivery_address"] or "", "delivery_grid_id": row["delivery_grid_id"] or ""}
    except sqlite3.Error:
        pass
    return {}


def _destination(c, task: dict[str, Any]) -> tuple[float | None, float | None, str, str, str]:
    mode = _leg_mode(task)
    delivery = _delivery(c, task.get("shipment_number")) if mode == "DELIVERY" else {}
    grid_id = delivery.get("delivery_grid_id") or ""
    address = delivery.get("delivery_address") or ""
    if grid_id:
        try:
            resolved = core_address(grid_id)
            lat, lon = resolved.get("latitude"), resolved.get("longitude")
            if lat is not None and lon is not None:
                return float(lat), float(lon), grid_id, address, grid_id
        except HTTPException:
            pass
    lat, lon = task.get("latitude"), task.get("longitude")
    if lat is not None and lon is not None and not (mode == "DELIVERY" and grid_id):
        return float(lat), float(lon), grid_id, address, f"{lat},{lon}"
    return None, None, grid_id, address, grid_id or address or str(task.get("location_text") or "")


def _route(start_lat: float, start_lon: float, dest_lat: float, dest_lon: float) -> dict[str, Any] | None:
    key = (round(start_lat, 4), round(start_lon, 4), round(dest_lat, 5), round(dest_lon, 5))
    cached = _ROUTE_CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] < CACHE_TTL_S:
        return {**cached[1], "cache_hit": True}
    try:
        result = core_route(start_lat=start_lat, start_lon=start_lon, dest_lat=dest_lat, dest_lon=dest_lon, mode="driving")
    except HTTPException:
        return None
    route = {
        "distance_m": float(result.get("distance_m") or 0),
        "duration_s": float(result.get("duration_s") or 0),
        "provider": result.get("provider") or "ugamap",
        "points": result.get("points") or [],
        "cache_hit": False,
    }
    _ROUTE_CACHE[key] = (now, route)
    return route


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _active_reports() -> list[dict[str, Any]]:
    try:
        payload = core_reports()
        rows = list(payload.get("results") or []) if isinstance(payload, dict) else []
    except Exception:
        return []
    return [r for r in rows if str(r.get("status") or "new").lower() != "resolved"]


def _route_incidents(route: dict[str, Any] | None, reports: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    if not route or not route.get("points") or not reports:
        return [], 0
    points = route["points"]
    stride = max(1, len(points) // 220)
    sampled = points[::stride]
    hits = []
    delay_s = 0
    for rep in reports:
        try:
            lat, lon = float(rep.get("lat")), float(rep.get("lon"))
        except (TypeError, ValueError):
            continue
        category = str(rep.get("category") or "").lower()
        nearest = min((_haversine_m(float(p[0]), float(p[1]), lat, lon) for p in sampled), default=1e12)
        if nearest > INCIDENT_CORRIDOR_M:
            continue
        penalty = INCIDENT_DELAY_S.get(category, 0)
        # Unverified community reports remain visible but get half operational weight.
        community = str(rep.get("community_status") or "unverified").lower()
        if penalty and community == "unverified":
            penalty = int(penalty * 0.5)
        delay_s += penalty
        hits.append({
            "id": rep.get("id"),
            "category": category,
            "note": str(rep.get("note") or "")[:120],
            "distance_to_route_m": int(round(nearest)),
            "community_status": community,
            "operational_penalty_seconds": penalty,
            "affects_sequencing": bool(penalty),
        })
    hits.sort(key=lambda x: (not x["affects_sequencing"], x["distance_to_route_m"]))
    return hits[:8], delay_s


def _score(task: dict[str, Any], route: dict[str, Any] | None, incident_delay_s: int = 0) -> tuple[float, str]:
    now = time.time()
    status = str(task.get("status") or "").lower()
    notes = str(task.get("notes") or "").lower()
    urgent = any(k in notes for k in ("urgent", "priority", "asap", "expedite"))
    scheduled = float(task["scheduled_at"]) if task.get("scheduled_at") else None
    overdue = bool(scheduled and scheduled < now)
    score = 0.0
    reason = "UGAMAP ROAD TIME"
    if status in IN_PROGRESS:
        score -= 100000
        reason = "CONTINUE ACTIVE STOP"
    if urgent:
        score -= 30000
        reason = "URGENT / PRIORITY"
    if overdue:
        score -= 20000
        reason = "SCHEDULE WINDOW DUE"
    if scheduled:
        score += max(-5000, min(5000, (scheduled - now) / 60.0))
    if route:
        score += ((route["duration_s"] + incident_delay_s) / 60.0) * 10.0
        if incident_delay_s and reason == "UGAMAP ROAD TIME":
            reason = "ROAD INCIDENT AHEAD"
    else:
        score += 5000
    return score, reason


@router.get("")
def live_driver_routing(x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    start_lat, start_lon = d.get("current_lat"), d.get("current_lon")
    if start_lat is None or start_lon is None:
        return {
            "routing_available": False,
            "reason": "DRIVER_LOCATION_REQUIRED",
            "provider": "UGAMAP",
            "sequence": [],
            "next_stop": None,
        }
    reports = _active_reports()
    c = _conn()
    try:
        rows = [dict(x) for x in c.execute(
            "SELECT * FROM dispatch_tasks WHERE driver_id=? AND status NOT IN ('completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse') ORDER BY created_at",
            (d["id"],),
        ).fetchall()]
        enriched = []
        for task in rows[:MAX_ROUTED_STOPS]:
            dest_lat, dest_lon, grid_id, address, nav = _destination(c, task)
            route = _route(float(start_lat), float(start_lon), dest_lat, dest_lon) if dest_lat is not None and dest_lon is not None else None
            incidents, incident_delay_s = _route_incidents(route, reports)
            score, reason = _score(task, route, incident_delay_s)
            item = dict(task)
            item.update({
                "leg_mode": _leg_mode(task),
                "priority_reason": reason,
                "delivery_grid_id": grid_id,
                "delivery_address": address,
                "navigation_destination": nav,
                "ugamap_route_available": bool(route),
                "ugamap_provider": route.get("provider") if route else None,
                "road_distance_km": round(route["distance_m"] / 1000.0, 1) if route else None,
                "base_eta_minutes": max(1, int(round(route["duration_s"] / 60.0))) if route and route["duration_s"] > 0 else None,
                "incident_delay_minutes": int(round(incident_delay_s / 60.0)) if incident_delay_s else 0,
                "eta_minutes": max(1, int(round((route["duration_s"] + incident_delay_s) / 60.0))) if route and route["duration_s"] > 0 else None,
                "eta_confidence": "UGAMAP_ROUTE_PLUS_REPORTS" if incident_delay_s else ("LIVE_ROUTE" if route else "UNAVAILABLE"),
                "routing_cache_hit": route.get("cache_hit") if route else False,
                "route_incidents": incidents,
                "route_incident_count": len(incidents),
                "reroute_advisory": bool(incident_delay_s),
                "sequence_score": score,
            })
            enriched.append(item)
    finally:
        c.close()
    enriched.sort(key=lambda x: (x["sequence_score"], float(x.get("scheduled_at") or 9e18), float(x.get("created_at") or 0)))
    for idx, item in enumerate(enriched, 1):
        item["sequence"] = idx
        item.pop("sequence_score", None)
    next_stop = enriched[0] if enriched else None
    return {
        "routing_available": any(x["ugamap_route_available"] for x in enriched),
        "provider": "UGAMAP Core / Valhalla",
        "driver_location": {"latitude": start_lat, "longitude": start_lon},
        "sequencing_policy": "ACTIVE_WORK > URGENT > DUE_WINDOW > INCIDENT_ADJUSTED_UGAMAP_ROAD_TIME",
        "sequence": enriched,
        "next_stop": next_stop,
        "routed_stop_count": sum(1 for x in enriched if x["ugamap_route_available"]),
        "active_report_count": len(reports),
        "incident_aware": True,
        "reroute_advisory": bool(next_stop and next_stop.get("reroute_advisory")),
        "candidate_limit": MAX_ROUTED_STOPS,
        "cache_ttl_seconds": CACHE_TTL_S,
        "incident_corridor_meters": INCIDENT_CORRIDOR_M,
    }
