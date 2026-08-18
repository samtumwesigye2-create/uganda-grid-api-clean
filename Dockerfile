from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import json
import os

app = FastAPI(
    title="Uganda National Grid API",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Your actual database file
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

    q = q.lower().strip()

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

    search_id = grid_id.strip().lower()

    for item in addresses:

        stored_id = str(
            item.get("grid_id", "")
        ).strip().lower()

        if stored_id == search_id:
            return item


    return {
        "error": "Address not found",
        "searched": grid_id
    }



@app.get("/stats")
def stats():

    return {
        "database": "entebbe_database.json",
        "total_records": len(addresses)
    }
