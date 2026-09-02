from zip_population_policy import targets_for, policy_summary
from zipper_numbering import STATE_BLOCKS, SPECIAL_BLOCK, GEOGRAPHIC_BLOCK, format_zipper


def test_active_population_bands():
    urban = targets_for("Kampala")
    rural = targets_for("Buikwe")
    assert urban == {
        "density_class": "urban",
        "minimum": 3000,
        "target": 4500,
        "maximum": 6000,
    }
    assert rural == {
        "density_class": "rural",
        "minimum": 2000,
        "target": 3250,
        "maximum": 4500,
    }


def test_legacy_geographic_policy_is_retired():
    summary = policy_summary()
    assert summary["status"] == "active_replacement"
    assert summary["legacy_geographic_zips_active"] is False
    assert summary["format"] == "5-digit numeric"


def test_special_and_geographic_namespaces_do_not_overlap():
    assert SPECIAL_BLOCK == (0, 9999)
    assert GEOGRAPHIC_BLOCK == (10000, 99999)
    assert SPECIAL_BLOCK[1] < GEOGRAPHIC_BLOCK[0]


def test_ten_state_blocks_cover_geographic_namespace_without_overlap():
    blocks = sorted(STATE_BLOCKS.values())
    assert len(blocks) == 10
    assert blocks[0][0] == 10000
    assert blocks[-1][1] == 99999
    for start, end in blocks:
        assert end - start + 1 == 9000
        assert 10000 <= start <= end <= 99999
    for previous, current in zip(blocks, blocks[1:]):
        assert previous[1] + 1 == current[0]


def test_zipper_format_is_exactly_five_digits():
    assert format_zipper(0) == "00000"
    assert format_zipper(9999) == "09999"
    assert format_zipper(10000) == "10000"
    assert format_zipper(99999) == "99999"
