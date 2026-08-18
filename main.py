from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import json
from pathlib import Path


app = FastAPI(
    title="Uganda National Grid API"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent

DATABASE = BASE_DIR / "uganda_national_grid_addresses_v2.json"


with open(DATABASE, "r", encoding="utf-8") as file:
    addresses = json.load(file)



@app.get("/")
def home():

    if (BASE_DIR / "index.html").exists():
        return FileResponse(
            BASE_DIR / "index.html"
        )

    return {
        "message": "Uganda National Grid API is running"
    }



@app.get("/search")
def search(q: str = Query(...)):

    query = q.lower()

    results = []


    for place in addresses:

        searchable = json.dumps(place).lower()


        if query in searchable:


            results.append({

                "grid_id": place["grid_id"],

                "street": place["address"]["street"],

                "address": place["address"]["full_address"],

                "latitude": place["coordinates"]["latitude"],

                "longitude": place["coordinates"]["longitude"],

                "certification": place["certification"]

            })


    return {

        "count": len(results),

        "results": results

    }



@app.get("/health")
def health():

    return {
        "status": "ok",
        "records": len(addresses)
    }
