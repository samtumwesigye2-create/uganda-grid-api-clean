"""Population-first ZIP clustering for Uganda parishes.

Pipeline:
1) split oversized parishes (> MAX_POPULATION) into near-equal provisional units;
2) merge undersized units (< MIN_POPULATION) only with an adjacent unit in the
   same sub-county when the merged population stays <= MAX_POPULATION;
3) assign sequential 5-character ZIP strings from the district's fixed range;
4) fail loudly if the district range is exhausted.

Until village-level boundaries/populations are available, split pieces carry
geometry_status='population_placeholder'. The downstream merge/assignment
pipeline is intentionally independent of how the split units are produced.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Iterable, List, Dict, Any, Tuple

from national_zip_registry import STATE_BLOCKS

TARGET_POPULATION = 1650
MIN_POPULATION = 1000
MAX_POPULATION = 2500


def _norm_name(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("-", " ").split())


def district_range(district_name: str) -> Tuple[int, int, str, str]:
    """Return (start, end, state_key, canonical_district_name)."""
    wanted = _norm_name(district_name)
    matches = []
    for state_key, state in STATE_BLOCKS.items():
        for name, start, end in state["districts"]:
            canonical = _norm_name(name)
            aliases = {canonical}
            if canonical.endswith(" (district)"):
                aliases.add(canonical[:-11].strip())
            if canonical.endswith(" district"):
                aliases.add(canonical[:-9].strip())
            if canonical.endswith(" (city)"):
                aliases.add(canonical[:-7].strip())
            if wanted in aliases:
                matches.append((start, end, state_key, name))
    if not matches:
        raise ValueError(f"Unknown district: {district_name}")
    if len(matches) > 1:
        raise ValueError(f"Ambiguous district name: {district_name}")
    return matches[0]


def _validate_parish(row: Dict[str, Any], index: int) -> Dict[str, Any]:
    parish = str(row.get("parish") or row.get("parish_name") or "").strip()
    subcounty = str(row.get("subcounty") or row.get("sub_county") or "").strip()
    if not parish:
        raise ValueError(f"Row {index}: parish is required")
    if not subcounty:
        raise ValueError(f"Row {index}: subcounty is required")
    try:
        population = int(row.get("population"))
    except (TypeError, ValueError):
        raise ValueError(f"Row {index}: population must be an integer")
    if population <= 0:
        raise ValueError(f"Row {index}: population must be positive")
    out = deepcopy(row)
    out.update({"parish": parish, "subcounty": subcounty, "population": population})
    return out


def _even_integer_slices(total: int, count: int) -> List[int]:
    base, remainder = divmod(total, count)
    return [base + (1 if i < remainder else 0) for i in range(count)]


def split_oversized_parishes(
    parishes: Iterable[Dict[str, Any]],
    target_population: int = TARGET_POPULATION,
    max_population: int = MAX_POPULATION,
) -> List[Dict[str, Any]]:
    """Split each oversized parish into deterministic, near-equal pieces."""
    if target_population <= 0 or max_population <= 0:
        raise ValueError("Population thresholds must be positive")
    units: List[Dict[str, Any]] = []
    for index, raw in enumerate(parishes):
        row = _validate_parish(raw, index)
        pop = row["population"]
        split_count = math.ceil(pop / target_population) if pop > max_population else 1
        # Guard against a custom target that would accidentally leave a slice > cap.
        split_count = max(split_count, math.ceil(pop / max_population))
        pieces = _even_integer_slices(pop, split_count)
        for split_index, piece_pop in enumerate(pieces, start=1):
            unit = deepcopy(row)
            unit.update({
                "population": piece_pop,
                "source_parish": row["parish"],
                "split_index": split_index,
                "split_count": split_count,
                "is_split": split_count > 1,
                "geometry_status": "population_placeholder" if split_count > 1 else row.get("geometry_status", "parish_boundary"),
                "source_unit_ids": [f"{row['subcounty']}::{row['parish']}::{split_index}"],
            })
            units.append(unit)
    return units


def _merged_unit(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    names = []
    for item in (left, right):
        for name in item.get("source_parishes", [item.get("source_parish", item.get("parish"))]):
            if name and name not in names:
                names.append(name)
    merged = {
        "parish": " + ".join(names),
        "subcounty": left["subcounty"],
        "population": int(left["population"]) + int(right["population"]),
        "source_parishes": names,
        "source_unit_ids": list(left.get("source_unit_ids", [])) + list(right.get("source_unit_ids", [])),
        "is_split": bool(left.get("is_split") or right.get("is_split")),
        "is_merged": True,
        "geometry_status": "population_placeholder" if (
            left.get("geometry_status") == "population_placeholder" or right.get("geometry_status") == "population_placeholder"
        ) else "administrative_merge",
    }
    return merged


def merge_undersized_units(
    units: Iterable[Dict[str, Any]],
    min_population: int = MIN_POPULATION,
    target_population: int = TARGET_POPULATION,
    max_population: int = MAX_POPULATION,
) -> List[Dict[str, Any]]:
    """Merge sub-1,000 units with an immediate same-sub-county neighbor.

    The candidate producing a population closest to TARGET is preferred. A merge
    that exceeds MAX is never allowed. If no legal adjacent merge exists, the
    unit remains and is flagged for review rather than violating the hard cap.
    """
    work = [deepcopy(u) for u in units]
    i = 0
    while i < len(work):
        current = work[i]
        if int(current["population"]) >= min_population:
            i += 1
            continue

        candidates = []
        for neighbor_index in (i - 1, i + 1):
            if neighbor_index < 0 or neighbor_index >= len(work):
                continue
            neighbor = work[neighbor_index]
            if _norm_name(neighbor.get("subcounty")) != _norm_name(current.get("subcounty")):
                continue
            combined = int(current["population"]) + int(neighbor["population"])
            if combined <= max_population:
                candidates.append((abs(target_population - combined), neighbor_index, combined))

        if not candidates:
            current["under_minimum_review"] = True
            i += 1
            continue

        _, neighbor_index, _ = min(candidates, key=lambda x: (x[0], abs(x[1] - i), x[1]))
        if neighbor_index < i:
            merged = _merged_unit(work[neighbor_index], current)
            work[neighbor_index:i + 1] = [merged]
            i = max(0, neighbor_index)
        else:
            merged = _merged_unit(current, work[neighbor_index])
            work[i:neighbor_index + 1] = [merged]
            # Re-evaluate the merged unit in case it is still below minimum.
    return work


def assign_district_zips(units: Iterable[Dict[str, Any]], district_name: str) -> List[Dict[str, Any]]:
    start, end, state_key, canonical_district = district_range(district_name)
    work = [deepcopy(u) for u in units]
    capacity = end - start + 1
    if len(work) > capacity:
        raise RuntimeError(
            f"District ZIP range exhausted for {canonical_district}: "
            f"needs {len(work)} ZIPs but range {start:05d}-{end:05d} has {capacity}"
        )
    assigned = []
    for offset, unit in enumerate(work):
        pop = int(unit["population"])
        if pop > MAX_POPULATION:
            raise ValueError(f"Unit exceeds hard population cap: {unit.get('parish')} = {pop}")
        item = deepcopy(unit)
        item.update({
            "zip_code": f"{start + offset:05d}",
            "district": canonical_district,
            "state_key": state_key,
            "district_zip_range": f"{start:05d}-{end:05d}",
            "population_target": TARGET_POPULATION,
            "population_min": MIN_POPULATION,
            "population_max": MAX_POPULATION,
        })
        assigned.append(item)
    return assigned


def build_district_zip_clusters(parishes: Iterable[Dict[str, Any]], district_name: str) -> Dict[str, Any]:
    """Run the complete split -> merge -> assign pipeline."""
    source = [_validate_parish(row, i) for i, row in enumerate(parishes)]
    split = split_oversized_parishes(source)
    merged = merge_undersized_units(split)
    assigned = assign_district_zips(merged, district_name)
    start, end, state_key, canonical_district = district_range(district_name)
    return {
        "district": canonical_district,
        "state_key": state_key,
        "district_zip_range": f"{start:05d}-{end:05d}",
        "source_parishes": len(source),
        "source_population": sum(x["population"] for x in source),
        "split_units": len(split),
        "assigned_zip_units": len(assigned),
        "remaining_capacity": (end - start + 1) - len(assigned),
        "under_minimum_review_count": sum(1 for x in assigned if x.get("under_minimum_review")),
        "clusters": assigned,
    }
