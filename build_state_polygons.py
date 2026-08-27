"""Build Uganda National Grid's ten custom state polygons.

Input: Uganda district GeoJSON FeatureCollection.
Output: GeoJSON FeatureCollection with exactly ten dissolved state geometries.

Requires shapely. The build fails closed on unmatched district names, invalid
geometry, overlaps, or a source district count other than 136.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from state_district_registry import DISTRICT_TO_STATE, validate_assignment
from state_regions import STATE_REGIONS


def _district_name(feature):
    p = feature.get("properties") or {}
    for key in ("name", "NAME", "district", "DISTRICT", "District"):
        value = p.get(key)
        if value:
            return str(value).strip()
    raise ValueError("District feature has no recognized name property")


def build(source):
    features = source.get("features") or []
    names = [_district_name(f) for f in features]
    check = validate_assignment(names)
    if not check["ready_for_dissolve"]:
        raise ValueError(f"District registry reconciliation failed: {check}")

    grouped = defaultdict(list)
    for feature in features:
        name = _district_name(feature)
        geom = shape(feature["geometry"])
        if geom.is_empty or not geom.is_valid:
            raise ValueError(f"Invalid source geometry: {name}")
        grouped[DISTRICT_TO_STATE[name]].append(geom)

    out = []
    dissolved = {}
    for code, meta in STATE_REGIONS.items():
        geoms = grouped.get(code, [])
        if not geoms:
            raise ValueError(f"State {code} has no district polygons")
        geom = unary_union(geoms)
        if geom.is_empty or not geom.is_valid:
            raise ValueError(f"Invalid dissolved state geometry: {code}")
        dissolved[code] = geom
        out.append({
            "type": "Feature",
            "properties": {
                "state_code": code,
                "state_name": meta["name"],
                "grid_prefix": meta["grid_prefix"],
                "postal_prefix": meta["postal_prefix"],
                "postal_center": meta["postal_center"],
                "district_count": len(geoms),
            },
            "geometry": mapping(geom),
        })

    overlaps = []
    codes = list(dissolved)
    for i, a in enumerate(codes):
        for b in codes[i + 1:]:
            inter = dissolved[a].intersection(dissolved[b])
            # Shared borders are valid; positive-area intersections are not.
            if not inter.is_empty and inter.area > 1e-12:
                overlaps.append({"states": [a, b], "area_deg2": inter.area})
    if overlaps:
        raise ValueError(f"State polygon overlaps detected: {overlaps}")

    source_union = unary_union([shape(f["geometry"]) for f in features])
    state_union = unary_union(list(dissolved.values()))
    missing = source_union.difference(state_union)
    extra = state_union.difference(source_union)
    if missing.area > 1e-12 or extra.area > 1e-12:
        raise ValueError(
            f"Coverage mismatch: missing={missing.area}, extra={extra.area}"
        )

    return {
        "type": "FeatureCollection",
        "name": "uganda_national_grid_10_states",
        "properties": {
            "state_count": 10,
            "district_count": len(features),
            "coverage_validated": True,
            "overlap_validated": True,
        },
        "features": out,
    }


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: python build_state_polygons.py districts.geojson state_polygons.geojson")
    source_path, output_path = map(Path, sys.argv[1:])
    source = json.loads(source_path.read_text(encoding="utf-8"))
    result = build(source)
    output_path.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(f"OK: wrote {len(result['features'])} validated state polygons to {output_path}")


if __name__ == "__main__":
    main()
