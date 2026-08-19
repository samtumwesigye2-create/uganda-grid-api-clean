from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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

DATABASE = os.path.join(
    BASE_DIR,
    "entebbe_database.json"
)

try:
    with open(DATABASE, "r", encoding="utf-8") as file:
        addresses = json.load(file)

    print(f"Loaded {len(addresses)} addresses")

except Exception as e:
    print("Database loading failed:", e)
    addresses = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home():

    return """
<!DOCTYPE html>
<html>
<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Uganda National Grid</title>

<link
rel="stylesheet"
href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
/>

<style>

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f4f6f8;
}

header {
    background: #111827;
    color: white;
    padding: 20px;
    text-align: center;
}

header h1 {
    margin: 0;
}

.search {
    background: white;
    max-width: 1000px;
    margin: 20px auto;
    padding: 20px;
    border-radius: 12px;
}

input {
    width: 100%;
    box-sizing: border-box;
    padding: 13px;
    margin: 6px 0 12px;
    border: 1px solid #ccc;
    border-radius: 7px;
    font-size: 16px;
}

button {
    padding: 13px 22px;
    background: #d71920;
    color: white;
    border: 0;
    border-radius: 7px;
    font-size: 16px;
}

#map {
    height: 600px;
    max-width: 1100px;
    margin: 20px auto;
    border-radius: 12px;
}

</style>

</head>

<body>

<header>

<h1>Uganda National Grid</h1>

<p>
National transportation and infrastructure network
</p>

</header>

<div class="search">

<label>Start Location</label>

<input
id="start"
placeholder="Enter starting location"
/>

<label>Destination</label>

<input
id="destination"
placeholder="Enter destination"
/>

<button onclick="findRoute()">
Find Route
</button>

</div>

<div id="map"></div>

<script
src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js">
</script>

<script>

const map = L.map("map").setView(
    [1.3733, 32.2903],
    7
);

L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        maxZoom: 19,
        attribution:
        "&copy; OpenStreetMap contributors"
    }
).addTo(map);


/* Uganda cities */

const cities = [

["Kampala", 0.3476, 32.5825],

["Jinja", 0.4479, 33.2026],

["Mbarara", -0.6072, 30.6545],

["Mbale", 1.0821, 34.1750],

["Gulu", 2.7746, 32.2990],

["Arua", 3.0303, 30.9111],

["Soroti", 1.7146, 33.6111],

["Moroto", 2.5345, 34.6666],

["Hoima", 1.4331, 31.3524],

["Masaka", -0.3476, 31.7330]

];


cities.forEach(city => {

    L.marker([
        city[1],
        city[2]
    ])
    .addTo(map)
    .bindPopup(
        "<strong>" + city[0] + "</strong>"
    );

});


/* National Grid */

const routes = [

[
[0.3476,32.5825],
[0.4479,33.2026],
[1.0821,34.1750]
],

[
[0.3476,32.5825],
[-0.3476,31.7330],
[-0.6072,30.6545]
],

[
[0.3476,32.5825],
[1.4331,31.3524],
[2.7746,32.2990],
[3.0303,30.9111]
],

[
[1.0821,34.1750],
[1.7146,33.6111],
[2.5345,34.6666]
]

];


routes.forEach(route => {

    L.polyline(
        route,
        {
            color: "#d71920",
            weight: 4
        }
    ).addTo(map);

});


function findRoute() {

    const start =
        document.getElementById("start").value;

    const destination =
        document.getElementById("destination").value;

    if (!start || !destination) {

        alert(
            "Please enter both locations."
        );

        return;
    }

    alert(
        "Route requested from " +
        start +
        " to " +
        destination
    );
}

</script>

</body>
</html>
"""


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
        "database": "entebbe_database.json"
    }
