from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import json
import os


app = FastAPI(
    title="Uganda National Grid API",
    version="1.0"
)


@app.get("/health")
def health():
    return {"status": "ok"}


# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Database location
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
def search(q: str = Query(...)):

    q = q.strip().lower()

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

    search_id = grid_id.strip()

    for item in addresses:

        stored_id = str(
            item.get("grid_id", "")
        ).strip()

        if stored_id == search_id:
            return item

    return {
        "error": "Address not found",
        "searched": search_id
    }


@app.get("/stats")
def stats():

    return {
        "total_records": len(addresses),
        "database": "uganda_national_grid_addresses_v2.json"
    }
