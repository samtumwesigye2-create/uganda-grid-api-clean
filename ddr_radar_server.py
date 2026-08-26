from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from collections import deque
import math
import time
import uuid

app = FastAPI(title="DDR Radar Node", version="2.0E")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SENSOR_ID = "DDR-RADAR-001"
TRACK_TIMEOUT = 5.0
MAX_RANGE_DIFFERENCE_M = 150.0
MAX_BEARING_DIFFERENCE_DEG = 12.0
HISTORY_LENGTH = 30
EARTH_RADIUS_M = 6_371_000.0

# TEST GEOMETRY ONLY. Replace with surveyed receiver/transmitter coordinates.
RECEIVER_LAT = 38.9000
RECEIVER_LON = -77.0400
TRANSMITTER_LAT = 38.9500
TRANSMITTER_LON = -77.1000

tracks = {}


class RadarDetection(BaseModel):
    bistatic_range_m: float = Field(ge=0)
    bearing_deg: float = Field(ge=0, lt=360)
    radial_speed_mps: Optional[float] = None
    snr_db: float
    confidence: float = Field(ge=0, le=1)


def haversine_m(lat1, lon1, lat2, lon2):
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def initial_bearing_deg(lat1, lon1, lat2, lon2):
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(p2)
    x = (
        math.cos(p1) * math.sin(p2)
        - math.sin(p1) * math.cos(p2) * math.cos(dlambda)
    )
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def destination_point(lat, lon, bearing_deg, distance_m):
    phi1 = math.radians(lat)
    lam1 = math.radians(lon)
    theta = math.radians(bearing_deg)
    delta = distance_m / EARTH_RADIUS_M

    sin_phi2 = (
        math.sin(phi1) * math.cos(delta)
        + math.cos(phi1) * math.sin(delta) * math.cos(theta)
    )
    phi2 = math.asin(max(-1.0, min(1.0, sin_phi2)))
    lam2 = lam1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    lon2 = (math.degrees(lam2) + 540.0) % 360.0 - 180.0
    return math.degrees(phi2), lon2


BASELINE_M = haversine_m(
    RECEIVER_LAT, RECEIVER_LON,
    TRANSMITTER_LAT, TRANSMITTER_LON
)

TX_BEARING_DEG = initial_bearing_deg(
    RECEIVER_LAT, RECEIVER_LON,
    TRANSMITTER_LAT, TRANSMITTER_LON
)


def bearing_difference(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def bistatic_to_receiver_range(bistatic_excess_m, target_bearing_deg):
    b = float(bistatic_excess_m)
    theta = math.radians(bearing_difference(target_bearing_deg, TX_BEARING_DEG))
    d = BASELINE_M
    denominator = 2.0 * (b + d - d * math.cos(theta))
    if abs(denominator) < 1e-9:
        raise ValueError("Degenerate bistatic geometry")
    r = (b * (b + 2.0 * d)) / denominator
    if r < 0 or not math.isfinite(r):
        raise ValueError("Invalid bistatic solution")
    return r


def estimate_position(bistatic_excess_m, bearing_deg):
    receiver_range_m = bistatic_to_receiver_range(
        bistatic_excess_m,
        bearing_deg
    )
    lat, lon = destination_point(
        RECEIVER_LAT,
        RECEIVER_LON,
        bearing_deg,
        receiver_range_m
    )
    return {
        "receiver_range_m": round(receiver_range_m, 2),
        "latitude": round(lat, 7),
        "longitude": round(lon, 7),
    }


def expire_tracks():
    now = time.time()
    expired = [
        track_id
        for track_id, track in tracks.items()
        if now - track["last_seen"] > TRACK_TIMEOUT
    ]
    for track_id in expired:
        del tracks[track_id]


def find_track(detection):
    best_track = None
    best_score = math.inf
    for track in tracks.values():
        range_error = abs(
            track["bistatic_range_m"] - detection.bistatic_range_m
        )
        bearing_error = bearing_difference(
            track["bearing_deg"],
            detection.bearing_deg
        )
        if range_error > MAX_RANGE_DIFFERENCE_M:
            continue
        if bearing_error > MAX_BEARING_DIFFERENCE_DEG:
            continue
        score = range_error + bearing_error * 10.0
        if score < best_score:
            best_score = score
            best_track = track
    return best_track


def calculate_motion(track):
    history = track["history"]
    if len(history) < 2:
        return {"range_rate_mps": None, "motion": "UNKNOWN"}
    first = history[0]
    last = history[-1]
    dt = last["timestamp"] - first["timestamp"]
    if dt <= 0:
        return {"range_rate_mps": None, "motion": "UNKNOWN"}
    rate = (last["receiver_range_m"] - first["receiver_range_m"]) / dt
    if rate < -2:
        motion = "APPROACHING"
    elif rate > 2:
        motion = "RECEDING"
    else:
        motion = "CROSSING_OR_STATIONARY"
    return {"range_rate_mps": round(rate, 2), "motion": motion}


def track_to_feature(track):
    motion = calculate_motion(track)
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [track["longitude"], track["latitude"]],
        },
        "properties": {
            "sensor_id": track["sensor_id"],
            "track_id": track["track_id"],
            "status": track["status"],
            "hits": track["hits"],
            "bearing_deg": track["bearing_deg"],
            "bistatic_range_m": track["bistatic_range_m"],
            "receiver_range_m": track["receiver_range_m"],
            "radial_speed_mps": track["radial_speed_mps"],
            "range_rate_mps": motion["range_rate_mps"],
            "motion": motion["motion"],
            "snr_db": track["snr_db"],
            "confidence": track["confidence"],
            "last_seen": track["last_seen"],
        },
    }


@app.get("/health")
def health():
    expire_tracks()
    return {
        "sensor_id": SENSOR_ID,
        "status": "ONLINE",
        "active_tracks": len(tracks),
        "timestamp": time.time(),
    }


@app.post("/radar/detection")
def radar_detection(data: RadarDetection):
    expire_tracks()
    now = time.time()
    position = estimate_position(data.bistatic_range_m, data.bearing_deg)
    track = find_track(data)

    point = {
        "timestamp": now,
        "bistatic_range_m": data.bistatic_range_m,
        "receiver_range_m": position["receiver_range_m"],
        "bearing_deg": data.bearing_deg,
        "latitude": position["latitude"],
        "longitude": position["longitude"],
    }

    if track is None:
        track_id = "DDR-" + uuid.uuid4().hex[:8].upper()
        history = deque(maxlen=HISTORY_LENGTH)
        history.append(point)
        track = {
            "sensor_id": SENSOR_ID,
            "track_id": track_id,
            "created": now,
            "last_seen": now,
            "hits": 1,
            "status": "TENTATIVE",
            "bistatic_range_m": data.bistatic_range_m,
            "receiver_range_m": position["receiver_range_m"],
            "bearing_deg": data.bearing_deg,
            "radial_speed_mps": data.radial_speed_mps,
            "latitude": position["latitude"],
            "longitude": position["longitude"],
            "snr_db": data.snr_db,
            "confidence": data.confidence,
            "history": history,
        }
        tracks[track_id] = track
    else:
        track["last_seen"] = now
        track["hits"] += 1
        track["bistatic_range_m"] = data.bistatic_range_m
        track["receiver_range_m"] = position["receiver_range_m"]
        track["bearing_deg"] = data.bearing_deg
        track["radial_speed_mps"] = data.radial_speed_mps
        track["latitude"] = position["latitude"]
        track["longitude"] = position["longitude"]
        track["snr_db"] = data.snr_db
        track["confidence"] = data.confidence
        track["history"].append(point)
        if track["hits"] >= 3:
            track["status"] = "CONFIRMED"

    return track_to_feature(track)


@app.get("/radar/tracks.geojson")
def radar_tracks_geojson():
    expire_tracks()
    return {
        "type": "FeatureCollection",
        "sensor_id": SENSOR_ID,
        "timestamp": time.time(),
        "features": [
            track_to_feature(track)
            for track in tracks.values()
            if track["status"] == "CONFIRMED"
        ],
    }
