"""DDR V2.0E end-to-end smoke test.

Run while ddr_radar_server.py is listening on localhost:8001.
Posts three associated detections, verifies confirmation, then verifies that
/radar/tracks.geojson exposes the confirmed map target.
"""

import json
import time
import urllib.request

BASE_URL = "http://127.0.0.1:8001"

DETECTIONS = [
    {"bistatic_range_m": 900.0, "bearing_deg": 72.0, "radial_speed_mps": -10.0, "snr_db": 13.5, "confidence": 0.82},
    {"bistatic_range_m": 870.0, "bearing_deg": 71.8, "radial_speed_mps": -10.5, "snr_db": 14.0, "confidence": 0.86},
    {"bistatic_range_m": 840.0, "bearing_deg": 71.5, "radial_speed_mps": -11.0, "snr_db": 14.4, "confidence": 0.91},
]


def request_json(path, method="GET", payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    health = request_json("/health")
    assert health["status"] == "ONLINE"
    print("HEALTH: ONLINE")

    last_feature = None
    for index, detection in enumerate(DETECTIONS, start=1):
        last_feature = request_json(
            "/radar/detection",
            method="POST",
            payload=detection,
        )
        props = last_feature["properties"]
        print(
            f"HIT {index}: {props['track_id']} "
            f"{props['status']} bearing={props['bearing_deg']}"
        )
        time.sleep(0.25)

    assert last_feature is not None
    assert last_feature["properties"]["status"] == "CONFIRMED"

    feed = request_json("/radar/tracks.geojson")
    assert feed["type"] == "FeatureCollection"
    assert len(feed["features"]) >= 1

    track_id = last_feature["properties"]["track_id"]
    match = next(
        (f for f in feed["features"] if f["properties"]["track_id"] == track_id),
        None,
    )
    assert match is not None

    lon, lat = match["geometry"]["coordinates"]
    print(f"MAP READY: {track_id} @ {lat}, {lon}")
    print("DDR V2.0E E2E: PASS")


if __name__ == "__main__":
    main()
