"""Population-balanced national ZIPPER generator.

This is the active replacement ZIPPER system for UGAMAP; the old system is retired.
Population targets:
  - major-city districts: 3,000-6,000 people per ZIPPER (target 4,500)
  - rural/other districts: 2,000-4,500 people per ZIPPER (target 3,250)

The generator consumes parish GeoJSON plus a parish population lookup. Splits
are area-based estimates whenever population is not available below parish
level. ZIPPER IDs are plain five-digit numeric codes: 00001-99999.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Optional

from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union

URBAN_MIN = 3000
URBAN_MAX = 6000
URBAN_TARGET = 4500
RURAL_MIN = 2000
RURAL_MAX = 4500
RURAL_TARGET = 3250

MAJOR_CITY_DISTRICTS = {
    "Kampala", "Wakiso", "Mukono", "Jinja", "Mbarara", "Mbale",
    "Gulu", "Arua", "Masaka", "Soroti", "Hoima", "Lira"
}

@dataclass
class Parish:
    name: str
    district: str
    subcounty: str
    population: int
    geometry: object


def targets_for(district: str):
    if str(district).strip() in MAJOR_CITY_DISTRICTS:
        return URBAN_MIN, URBAN_MAX, URBAN_TARGET, "urban"
    return RURAL_MIN, RURAL_MAX, RURAL_TARGET, "rural"


def load_parishes(geojson_path: str, population_lookup: Optional[dict] = None,
                   name_field: str = "PARISH_NAME",
                   district_field: str = "DISTRICT_NAME",
                   subcounty_field: str = "SUBCOUNTY_NAME") -> list[Parish]:
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for feat in data.get("features", []):
        p = feat.get("properties") or {}
        name = p.get(name_field) or p.get("NAME_4") or p.get("ADM4_EN") or "UNKNOWN"
        district = p.get(district_field) or p.get("NAME_1") or p.get("ADM1_EN") or "UNKNOWN"
        subcounty = p.get(subcounty_field) or p.get("NAME_3") or p.get("ADM3_EN") or "UNKNOWN"
        pop = int((population_lookup or {}).get(name, 0) or 0)
        out.append(Parish(name, district, subcounty, pop, shape(feat["geometry"])))
    return out


def split_polygon(geom, n: int):
    if n <= 1:
        return [geom]
    minx, miny, maxx, maxy = geom.bounds
    width, height = maxx - minx, maxy - miny
    ratio = width / height if height else 1.0
    cols = max(1, round(math.sqrt(n * ratio)))
    rows = max(1, math.ceil(n / cols))
    pieces = []
    for r in range(rows):
        for c in range(cols):
            cell = box(minx + width*c/cols, miny + height*r/rows,
                       minx + width*(c+1)/cols, miny + height*(r+1)/rows)
            clipped = geom.intersection(cell)
            if not clipped.is_empty and clipped.area > 0:
                pieces.append(clipped)
    return pieces or [geom]


def _zone(parish: Parish, geom, population: int, status: str):
    lo, hi, target, density = targets_for(parish.district)
    return {
        "district": parish.district,
        "subcounty": parish.subcounty,
        "source_parish": parish.name,
        "population": int(population),
        "population_min": lo,
        "population_max": hi,
        "population_target": target,
        "density_class": density,
        "geometry_status": status,
        "layer": "ZIPPER",
        "geometry": geom,
    }


def split_parish(parish: Parish):
    lo, hi, target, _ = targets_for(parish.district)
    if parish.population <= hi:
        return [_zone(parish, parish.geometry, parish.population, "verified_boundary")]
    n = max(1, round(parish.population / target))
    n_min = max(1, math.ceil(parish.population / hi))
    n_max = max(1, math.floor(parish.population / lo))
    n = min(max(n, n_min), n_max) if n_max >= n_min else n_min
    pieces = split_polygon(parish.geometry, n)
    total_area = sum(g.area for g in pieces) or 1.0
    return [_zone(parish, g, round(parish.population * g.area / total_area),
                  "area_split_estimate") for g in pieces]


def merge_small(zones: list[dict]):
    work = list(zones)
    changed = True
    while changed:
        changed = False
        for i, z in enumerate(work):
            lo, hi, _, _ = targets_for(z["district"])
            if z["population"] >= lo:
                continue
            candidates = []
            for j, other in enumerate(work):
                if i == j or other["district"] != z["district"]:
                    continue
                combined = z["population"] + other["population"]
                legal = lo <= combined <= hi
                touching = z["geometry"].touches(other["geometry"]) or z["geometry"].intersects(other["geometry"])
                candidates.append(((0 if legal else 1, 0 if touching else 1,
                                    z["geometry"].distance(other["geometry"]), combined), j))
            if not candidates:
                continue
            _, j = min(candidates, key=lambda x: x[0])
            a, b = z, work[j]
            merged = dict(a)
            merged["population"] = a["population"] + b["population"]
            merged["geometry"] = unary_union([a["geometry"], b["geometry"]])
            merged["source_parish"] = a["source_parish"] + "+" + b["source_parish"]
            merged["geometry_status"] = "merged_boundary"
            work = [x for k, x in enumerate(work) if k not in (i, j)] + [merged]
            changed = True
            break
    return work


def generate_zones(parishes: list[Parish]):
    zones = []
    for parish in parishes:
        zones.extend(split_parish(parish))
    return merge_small(zones)


def assign_zipper_ids(zones: list[dict], start: int = 1):
    """Assign plain five-digit ZIPPER codes: 00001, 00002, ... 99999."""
    ordered = sorted(zones, key=lambda z: (
        z["district"], -z["geometry"].representative_point().y,
        z["geometry"].representative_point().x
    ))
    if start < 0 or start + len(ordered) - 1 > 99999:
        raise ValueError("Five-digit ZIPPER namespace exhausted")
    for n, zone in enumerate(ordered, start=start):
        zone["zipper_id"] = f"{n:05d}"
    return ordered

# Backward-compatible function name for callers created during development.
def assign_zipper2_ids(zones: list[dict], start: int = 1):
    return assign_zipper_ids(zones, start)


def feature_collection(zones: list[dict]):
    features = []
    for z in zones:
        props = {k: v for k, v in z.items() if k != "geometry"}
        features.append({"type": "Feature", "properties": props,
                         "geometry": mapping(z["geometry"])})
    return {"type": "FeatureCollection", "features": features}


def export_geojson(zones: list[dict], out_path: str):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(feature_collection(assign_zipper_ids(zones)), f,
                  ensure_ascii=False, separators=(",", ":"))


def summary(zones: list[dict]):
    urban = [z for z in zones if z["density_class"] == "urban"]
    rural = [z for z in zones if z["density_class"] == "rural"]
    return {
        "layer": "ZIPPER",
        "zones": len(zones),
        "urban_zones": len(urban),
        "rural_zones": len(rural),
        "urban_range": [URBAN_MIN, URBAN_MAX],
        "rural_range": [RURAL_MIN, RURAL_MAX],
        "id_format": "00001-99999",
    }
