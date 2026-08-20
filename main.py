from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import json
import os

app = FastAPI(title="Uganda National Grid API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "entebbe_database.json")

try:
    with open(DATABASE, "r", encoding="utf-8") as f:
        addresses = json.load(f)
except Exception:
    addresses = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def stats():
    return {
        "total_records": len(addresses),
        "database": "entebbe_database.json"
    }


@app.get("/search")
def search(q: str = Query(...)):
    q = q.strip().lower()

    results = []

    for item in addresses:
        if q in json.dumps(item).lower():
            results.append(item)

    return {
        "count": len(results),
        "results": results[:50]
    }


@app.get("/", response_class=HTMLResponse)
def home():

    return """
<!DOCTYPE html>
<html>
<head>
<title>Uganda National Grid</title>

<link rel="stylesheet"
href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>

<style>
body{margin:0;font-family:Arial}
#map{height:90vh}
input,button{padding:12px;margin:5px}
</style>

</head>

<body>

<h2>Uganda National Grid</h2>

<input id="start" placeholder="Start">
<input id="destination" placeholder="Destination">

<button onclick="findRoute()">Find Route</button>

<div id="map"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<script>

const map=L.map("map").setView([1.3733,32.2903],7);

L.tileLayer(
"https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
).addTo(map);


let line=null;


async function findRoute(){

let start=document.getElementById("start").value;
let destination=document.getElementById("destination").value;


let a=await fetch("/search?q="+start);
let b=await fetch("/search?q="+destination);


let startData=await a.json();
let destData=await b.json();


if(!startData.results.length ||
!destData.results.length){

alert("Location not found");
return;

}


alert("Search connected successfully");

}

</script>

</body>
</html>
"""
