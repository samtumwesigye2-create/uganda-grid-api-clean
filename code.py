"""
zip_zone_generator.py
----------------------
Generates population-target ZIP zones (2,500-5,000 people per zone) from
real parish boundary polygons + parish population counts.

REAL BOUNDARY DATA SOURCE (use this instead of placeholder geometry):
  Uganda Subnational Administrative Boundaries (COD-AB), UBOS-sourced,
  hosted on the Humanitarian Data Exchange:
    https://data.humdata.org/dataset/cod-ab-uga
  Download: uga_admbnda_ubos_20200824_SHP.zip (or the GeoJSON export on
  the same page). Admin level 4 = parish, 1,520 features nationwide.
  This is real government-sourced parish geometry -- not a demo/placeholder
  shape like the current population_zip_clusters.geojson uses.

  NOTE: these boundaries are from 2020. The 2024 census may have created
  new parishes/subcounties since. Cross-check parish names against your
  2024 population source before trusting the join -- flag any parish name
  that doesn't match with source="boundary_2020_population_2024_unverified".

WHAT THIS SCRIPT DOES
  1. Loads parish polygons + population counts (population comes from your
     own 2024 data -- district_population.py / population_zip_geometry.py).
  2. Any parish ABOVE the target range gets SPLIT into N pieces.
  3. Any parish BELOW the target range gets MERGED with a neighbor.
  4. Assigns a ZIP code to every resulting zone.
  5. Writes output in the same GeoJSON schema as your existing
     population_zip_clusters.geojson, so it drops into the same pipeline.

LIMITATION (be upfront about this with anyone using the output):
  Splitting a parish uses a simple grid-bisection of its polygon, weighted
  by AREA, not by real intra-parish population distribution (we don't have
  village-level population). This means a split zone's population is an
  ESTIMATE (parish population / number of pieces), not a measurement.
  Every split zone is tagged geometry_status="area_split_estimate" so this
  is never silently presented as verified data.

REQUIRES: shapely (pip install shapely --break-system-packages)
"""

from __future__ import annotations
import json
import math
from dataclasses import dataclass, field
from typing import Optional

try:
    from shapely.geometry import shape, mapping, box
    from shapely.ops import unary_union
except ImportError as e:
    raise SystemExit(
        "This script needs shapely. Install with:\n"
        "    pip install shapely --break-system-packages\n"
        f"(original error: {e})"
    )

TARGET_MIN = 2500
TARGET_MAX = 5000
TARGET_MID = 3750  # used to decide how many pieces to split into


@dataclass
class Parish:
    name: str
    district: str
    subcounty: str
    population: int
    geometry: object  # shapely geometry
    neighbors: list = field(default_factory=list)  # filled in after load


# ---------------------------------------------------------------------------
# 1. LOAD
# ---------------------------------------------------------------------------

def load_parishes(geojson_path: str,
                   name_field: str = "PARISH_NAME",
                   district_field: str = "DISTRICT_NAME",
                   subcounty_field: str = "SUBCOUNTY_NAME",
                   population_lookup: Optional[dict] = None) -> list[Parish]:
    """
    Load parish polygons from the HDX/UBOS boundary GeoJSON.

    population_lookup: dict mapping parish name -> population count, coming
    from your existing 2024 population data (district_population.py). Field
    names in the UBOS file vary by export -- check the actual property keys
    in your downloaded file and adjust name_field/district_field/subcounty_field
    if they don't match (common alternates: "parish", "NAME_4", "ADM4_EN").
    """
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    parishes = []
    unmatched = []
    for feat in data["features"]:
        props = feat["properties"]
        name = props.get(name_field) or props.get("NAME_4") or props.get("ADM4_EN")
        district = props.get(district_field) or props.get("NAME_1") or props.get("ADM1_EN")
        subcounty = props.get(subcounty_field) or props.get("NAME_3") or props.get("ADM3_EN")
        geom = shape(feat["geometry"])

        pop = None
        if population_lookup:
            pop = population_lookup.get(name)
            if pop is None:
                unmatched.append(name)

        parishes.append(Parish(
            name=name or "UNKNOWN",
            district=district or "UNKNOWN",
            subcounty=subcounty or "UNKNOWN",
            population=pop or 0,
            geometry=geom,
        ))

    if unmatched:
        print(f"[warn] {len(unmatched)} parishes had no population match "
              f"(first 10: {unmatched[:10]}) -- these will need manual review.")

    return parishes


# ---------------------------------------------------------------------------
# 2. SPLIT oversized parishes
# ---------------------------------------------------------------------------

def split_polygon_grid(geom, n_pieces: int):
    """
    Split a polygon into ~n_pieces roughly-equal-area pieces using a simple
    grid clip over its bounding box. This is an AREA-based split (a stand-in
    for population density, since we don't have sub-parish population data).
    Returns a list of polygon pieces (only the parts that actually intersect
    the original parish, empties dropped).
    """
    if n_pieces <= 1:
        return [geom]

    minx, miny, maxx, maxy = geom.bounds
    width = maxx - minx
    height = maxy - miny

    # choose rows/cols close to a square grid, favoring the longer axis
    cols = max(1, round(math.sqrt(n_pieces * (width / height if height else 1))))
    rows = max(1, math.ceil(n_pieces / cols))

    pieces = []
    cell_w = width / cols
    cell_h = height / rows
    for r in range(rows):
        for c in range(cols):
            cell = box(minx + c * cell_w, miny + r * cell_h,
                       minx + (c + 1) * cell_w, miny + (r + 1) * cell_h)
            clipped = geom.intersection(cell)
            if not clipped.is_empty and clipped.area > 0:
                pieces.append(clipped)

    return pieces if pieces else [geom]


def split_oversized(parish: Parish) -> list[dict]:
    """Split a single parish into target-sized zones. Returns zone dicts."""
    n_pieces = max(1, round(parish.population / TARGET_MID))
    pieces = split_polygon_grid(parish.geometry, n_pieces)
    pop_per_piece = round(parish.population / len(pieces))

    zones = []
    for i, piece in enumerate(pieces):
        zones.append({
            "district": parish.district,
            "subcounty": parish.subcounty,
            "source_parish": parish.name,
            "population": pop_per_piece,
            "geometry": piece,
            "geometry_status": "area_split_estimate",
            "source": "2024_census_estimate",
        })
    return zones


# ---------------------------------------------------------------------------
# 3. MERGE undersized parishes
# ---------------------------------------------------------------------------

def merge_undersized(parishes: list[Parish]) -> list[dict]:
    """
    Greedily merge parishes below TARGET_MIN with their nearest unmerged
    neighbor (by centroid distance -- a proxy for adjacency since we don't
    require a full adjacency graph here) until each merged group falls in
    the target range or no more candidates remain in that district.
    """
    remaining = list(parishes)
    zones = []

    while remaining:
        current = remaining.pop(0)
        if current.population >= TARGET_MIN:
            zones.append({
                "district": current.district,
                "subcounty": current.subcounty,
                "source_parish": current.name,
                "population": current.population,
                "geometry": current.geometry,
                "geometry_status": "verified_boundary",
                "source": "2024_census_estimate",
            })
            continue

        # merge with nearest same-district neighbor until in range
        group = [current]
        group_pop = current.population
        group_geom = current.geometry
        centroid = current.geometry.centroid

        candidates = sorted(
            [p for p in remaining if p.district == current.district],
            key=lambda p: centroid.distance(p.geometry.centroid)
        )

        for cand in candidates:
            if group_pop >= TARGET_MIN:
                break
            group.append(cand)
            group_pop += cand.population
            group_geom = unary_union([group_geom, cand.geometry])
            remaining.remove(cand)

        zones.append({
            "district": current.district,
            "subcounty": current.subcounty,
            "source_parish": "+".join(p.name for p in group),
            "population": group_pop,
            "geometry": group_geom,
            "geometry_status": "merged_verified_boundary",
            "source": "2024_census_estimate",
        })

    return zones


# ---------------------------------------------------------------------------
# 4. ZIP ASSIGNMENT
# ---------------------------------------------------------------------------

def assign_zip_codes(zones: list[dict], district_blocks: dict[str, int]) -> list[dict]:
    """
    district_blocks: e.g. {"Kampala": 10000, "Wakiso": 11000}
    Assigns sequential ZIP codes within each district's reserved block.
    Matches the region-blocked numbering scheme already used in your
    zip_district_blocks.py -- reuse that file's ranges here instead of
    hardcoding new ones.
    """
    counters = dict(district_blocks)
    for zone in zones:
        d = zone["district"]
        if d not in counters:
            raise ValueError(f"No ZIP block reserved for district: {d}")
        zone["zip_code"] = str(counters[d])
        counters[d] += 1
    return zones


# ---------------------------------------------------------------------------
# 5. RUN + EXPORT
# ---------------------------------------------------------------------------

def generate_zones(parishes: list[Parish]) -> list[dict]:
    oversized = [p for p in parishes if p.population > TARGET_MAX]
    normal_or_under = [p for p in parishes if p.population <= TARGET_MAX]

    zones = []
    for p in oversized:
        zones.extend(split_oversized(p))
    zones.extend(merge_undersized(normal_or_under))
    return zones


def export_geojson(zones: list[dict], out_path: str):
    features = []
    for z in zones:
        props = {k: v for k, v in z.items() if k != "geometry"}
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": mapping(z["geometry"]),
        })
    fc = {"type": "FeatureCollection", "features": features}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fc, f)
    print(f"Wrote {len(features)} zones to {out_path}")


if __name__ == "__main__":
    # Example usage -- adjust paths once the real boundary file is downloaded
    # from https://data.humdata.org/dataset/cod-ab-uga
    #
    # population_lookup = load_population_from_2024_source(...)  # your own loader
    # parishes = load_parishes("uga_parish_boundaries.geojson", population_lookup=population_lookup)
    # zones = generate_zones(parishes)
    # zones = assign_zip_codes(zones, district_blocks={"Kampala": 10000, "Wakiso": 11000})
    # export_geojson(zones, "phase1_kampala_wakiso_zips.geojson")
    print(__doc__)
