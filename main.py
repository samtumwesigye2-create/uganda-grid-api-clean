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
    "uganda_national_grid_addresses_v2.json"
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

    q = q.lower().strip()

    exact = []
    matches = []

    for item in addresses:

        grid_id = str(
            item.get("grid_id", "")
        ).lower()

        house = str(
            item.get("house_number", "")
        ).lower()

        street = str(
            item.get("street", "")
        ).lower()

        city = str(
            item.get("city", "")
        ).lower()

        district = str(
            item.get("district_code", "")
        ).lower()

        address = str(
            item.get("address", "")
        ).lower()


        # Exact priority
        if (
            q == grid_id
            or q == house
        ):
            exact.append(item)


        # General search
        elif (
            q in grid_id
            or q in house
            or q in street
            or q in city
            or q in district
            or q in address
        ):
            matches.append(item)


    results = exact + matches


    return {
        "count": len(results),
        "results": results[:50]
    }


@app.get("/address/{grid_id}")
def get_address(grid_id: str):

    grid_id = grid_id.lower()

    for item in addresses:

        if item.get("grid_id", "").lower() == grid_id:
            return item


    return {
        "error": "Address not found"
    }
