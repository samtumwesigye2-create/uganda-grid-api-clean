from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import json
import os

app = FastAPI(
    title="Uganda National Grid API",
    version="1.0"
)

# Allow web app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Database file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(
    BASE_DIR,
    "entebbe_database.json"
)


# Load database
try:
    with open(DATABASE, "r", encoding="utf-8") as file:
        addresses = json.load(file)

    print(f"Loaded {len(addresses)} addresses")

except Exception as e:
    print("Database loading failed:", e)
    addresses = []


@app.get("/")
def home():
    return {
        "name": "Uganda National Grid API",
        "status": "online",
        "records": len(addresses)
    }


@app.get("/search")
def search(
    q: str = Query(...)
):
    q = q.lower()

    results = []

    for item in addresses:
        text = json.dumps(item).lower()

        if q in text:
            results.append(item)

    return {
        "count": len(results),
        "results": results[:50]
    }


@app.get("/address/{grid_id}")
def get_address(grid_id: str):

    for item in addresses:

        if item.get("grid_id") == grid_id:
            return item

    return {
        "error": "Address not found"
    }


@app.get("/nearby")
def nearby(
    lat: float,
    lon: float,
    radius: float = 0.01
):

    results = []

    for item in addresses:

        item_lat = float(item.get("latitude", 0))
        item_lon = float(item.get("longitude", 0))

        if (
            abs(item_lat - lat) <= radius
            and
            abs(item_lon - lon) <= radius
        ):
            results.append(item)

    return {
        "count": len(results),
        "results": results
    }
