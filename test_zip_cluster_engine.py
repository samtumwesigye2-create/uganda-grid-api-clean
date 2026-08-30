import unittest

from buikwe_county_2024_fixture import (
    BUIKWE_COUNTY_2024,
    EXPECTED_SOURCE_PARISHES,
    EXPECTED_SOURCE_POPULATION,
)
from zip_cluster_engine import (
    split_oversized_parishes,
    merge_undersized_units,
    build_district_zip_clusters,
    district_range,
)


class ZipClusterEngineTests(unittest.TestCase):
    def test_buikwe_range(self):
        start, end, _, district = district_range("Buikwe")
        self.assertEqual((start, end), (14600, 14999))
        self.assertEqual(district, "Buikwe")

    def test_buikwe_county_2024_official_baseline(self):
        """Lock the verified UBOS Buikwe County pilot baseline.

        This fixture is Buikwe County only, not the whole Buikwe District.
        Under the canonical split/merge rules it produces 131 ZIP clusters.
        """
        self.assertEqual(len(BUIKWE_COUNTY_2024), EXPECTED_SOURCE_PARISHES)
        self.assertEqual(EXPECTED_SOURCE_PARISHES, 31)
        self.assertEqual(
            sum(row["population"] for row in BUIKWE_COUNTY_2024),
            EXPECTED_SOURCE_POPULATION,
        )
        self.assertEqual(EXPECTED_SOURCE_POPULATION, 188879)

        result = build_district_zip_clusters(BUIKWE_COUNTY_2024, "Buikwe")
        self.assertEqual(result["source_parishes"], 31)
        self.assertEqual(result["source_population"], 188879)
        self.assertEqual(result["split_units"], 131)
        self.assertEqual(result["assigned_zip_units"], 131)
        self.assertEqual(result["under_minimum_review_count"], 0)
        self.assertEqual(result["remaining_capacity"], 269)

        clusters = result["clusters"]
        self.assertEqual(clusters[0]["zip_code"], "14600")
        self.assertEqual(clusters[-1]["zip_code"], "14730")
        self.assertEqual(
            [row["zip_code"] for row in clusters],
            [f"{14600 + i:05d}" for i in range(131)],
        )
        self.assertEqual(sum(row["population"] for row in clusters), 188879)
        self.assertTrue(all(1000 <= row["population"] <= 2500 for row in clusters))

    def test_kitazi_6097_splits_into_four_near_equal_units(self):
        rows = [{"subcounty": "Example SC", "parish": "Kitazi", "population": 6097}]
        units = split_oversized_parishes(rows)
        self.assertEqual(len(units), 4)
        self.assertEqual([u["population"] for u in units], [1525, 1524, 1524, 1524])
        self.assertEqual(sum(u["population"] for u in units), 6097)
        self.assertTrue(all(u["geometry_status"] == "population_placeholder" for u in units))
        self.assertTrue(all(u["source_parish"] == "Kitazi" for u in units))

    def test_small_adjacent_same_subcounty_units_merge(self):
        units = [
            {"subcounty": "Nkokonjeru", "parish": "Mulajje", "population": 700, "source_parish": "Mulajje", "source_unit_ids": ["a"]},
            {"subcounty": "Nkokonjeru", "parish": "Ward B", "population": 850, "source_parish": "Ward B", "source_unit_ids": ["b"]},
            {"subcounty": "Other", "parish": "Ward C", "population": 900, "source_parish": "Ward C", "source_unit_ids": ["c"]},
        ]
        merged = merge_undersized_units(units)
        self.assertEqual(merged[0]["population"], 1550)
        self.assertTrue(merged[0]["is_merged"])
        self.assertEqual(merged[1]["population"], 900)
        self.assertTrue(merged[1]["under_minimum_review"])

    def test_mulajje_nkokonjeru_merge_allowed_under_same_town_council(self):
        units = [
            {"subcounty": "Nkokonjeru Town Council", "parish": "Mulajje Ward", "population": 760, "source_parish": "Mulajje Ward", "source_unit_ids": ["mulajje-3"]},
            {"subcounty": "Nkokonjeru Town Council", "parish": "Nkokonjeru Ward", "population": 820, "source_parish": "Nkokonjeru Ward", "source_unit_ids": ["nkokonjeru-1"]},
        ]
        merged = merge_undersized_units(units)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["subcounty"], "Nkokonjeru Town Council")
        self.assertEqual(merged[0]["population"], 1580)
        self.assertEqual(merged[0]["source_parishes"], ["Mulajje Ward", "Nkokonjeru Ward"])
        self.assertFalse(merged[0].get("under_minimum_review", False))

    def test_never_merges_across_subcounty_boundary(self):
        units = [
            {"subcounty": "A", "parish": "Small A", "population": 700, "source_parish": "Small A", "source_unit_ids": ["a"]},
            {"subcounty": "B", "parish": "Small B", "population": 800, "source_parish": "Small B", "source_unit_ids": ["b"]},
        ]
        merged = merge_undersized_units(units)
        self.assertEqual(len(merged), 2)
        self.assertTrue(all(x.get("under_minimum_review") for x in merged))

    def test_pipeline_assigns_sequential_text_zips(self):
        rows = [
            {"subcounty": "SC1", "parish": "Kitazi", "population": 6097},
            {"subcounty": "SC1", "parish": "Small", "population": 900},
            {"subcounty": "SC1", "parish": "Neighbor", "population": 700},
        ]
        result = build_district_zip_clusters(rows, "Buikwe")
        zips = [x["zip_code"] for x in result["clusters"]]
        self.assertEqual(zips, [f"{14600+i:05d}" for i in range(len(zips))])
        self.assertTrue(all(isinstance(z, str) and len(z) == 5 for z in zips))
        self.assertEqual(result["source_population"], 7697)
        self.assertTrue(all(x["population"] <= 2500 for x in result["clusters"]))


if __name__ == "__main__":
    unittest.main()
