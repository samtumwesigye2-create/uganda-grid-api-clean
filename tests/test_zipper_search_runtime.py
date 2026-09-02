from shapely.geometry import mapping, box

import zipper_search_runtime as z


def _fake_fc():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "zipper_id": "12345",
                "zip_code": "12345",
                "district": "Kampala",
                "state_code": "KMP",
                "population": 4200,
            },
            "geometry": mapping(box(32.55, 0.30, 32.57, 0.32)),
        }],
    }


def test_lookup_five_digit_zipper(monkeypatch):
    monkeypatch.setattr(z, "live_zipper_feature_collection", _fake_fc)
    z._lookup_index.cache_clear()
    item = z.lookup_zipper("12345")
    assert item["grid_id"] == "12345"
    assert item["district"] == "Kampala"
    assert 0.30 <= item["latitude"] <= 0.32
    assert 32.55 <= item["longitude"] <= 32.57


def test_search_five_digit_zipper(monkeypatch):
    monkeypatch.setattr(z, "live_zipper_feature_collection", _fake_fc)
    z._lookup_index.cache_clear()
    result = z.search_zipper("12345")
    assert result["count"] == 1
    assert result["results"][0]["zipper_id"] == "12345"


def test_invalid_search_returns_empty():
    assert z.search_zipper("UG-ENT-000400") == {"count": 0, "results": []}
