from fastapi import FastAPI

app = FastAPI(title="Uganda National Grid API")


@app.get("/")
def root():
    return {
        "service": "Uganda National Grid API",
        "status": "online",
        "phase": 2
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/grid")
def grid():
    return {
        "country": "UG",
        "system": "Uganda National Grid",
        "status": "ready"
    }


@app.get("/address/{grid_id}")
def address(grid_id: str):
    return {
        "grid_id": grid_id,
        "country": "UG",
        "district": "Sample District",
        "subcounty": "Sample Subcounty",
        "parish": "Sample Parish",
        "building_id": "000245",
        "coordinates": {
            "latitude": 0.0,
            "longitude": 32.0
        }
    }
