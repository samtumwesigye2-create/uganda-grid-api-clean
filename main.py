@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Uganda National Grid</title>

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>

<style>
body {
    margin:0;
    font-family:Arial,sans-serif;
    background:#f4f6f8;
}

header {
    background:#111827;
    color:white;
    padding:20px;
    text-align:center;
}

.search {
    background:white;
    max-width:1000px;
    margin:20px auto;
    padding:20px;
    border-radius:12px;
}

input {
    width:100%;
    padding:13px;
    margin:7px 0 14px;
    border:1px solid #ccc;
    border-radius:7px;
    font-size:16px;
}

button {
    padding:13px 22px;
    background:#d71920;
    color:white;
    border:none;
    border-radius:7px;
    font-size:16px;
}

#map {
    height:600px;
    width:100%;
    max-width:1100px;
    margin:20px auto;
    border-radius:12px;
}
</style>

</head>

<body>

<header>
<h1>Uganda National Grid</h1>
<p>National transportation and infrastructure network</p>
</header>


<div class="search">

<label>Start Location</label>
<input id="start" placeholder="Enter starting location">


<label>Destination</label>
<input id="destination" placeholder="Enter destination">


<button onclick="findRoute()">Find Route</button>

</div>


<div id="map"></div>


<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>


<script>

const map = L.map("map").setView([1.3733,32.2903],7);


L.tileLayer(
"https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
{
maxZoom:19,
attribution:"&copy; OpenStreetMap contributors"
}
).addTo(map);



const cities = [

["Kampala",0.3476,32.5825],
["Entebbe",0.0512,32.4637],
["Jinja",0.4479,33.2026],
["Mbarara",-0.6072,30.6545],
["Mbale",1.0821,34.1750],
["Gulu",2.7746,32.2990],
["Arua",3.0303,30.9111],
["Soroti",1.7146,33.6111],
["Moroto",2.5345,34.6666],
["Hoima",1.4331,31.3524],
["Masaka",-0.3476,31.7330]

];


cities.forEach(city=>{

L.marker([city[1],city[2]])
.addTo(map)
.bindPopup(city[0]);

});



function findCity(name){

name=name.trim().toLowerCase();

for(const city of cities){

if(city[0].toLowerCase()===name){

return [city[1],city[2]];

}

}

return null;

}



let routeLine=null;



async function findRoute(){


const start=document.getElementById("start").value;

const destination=document.getElementById("destination").value;



const startCoords=findCity(start);

const destinationCoords=findCity(destination);



if(!startCoords || !destinationCoords){

alert("Use a major Ugandan city.");

return;

}



const url=

"https://router.project-osrm.org/route/v1/driving/"

+startCoords[1]+","+startCoords[0]

+";"

+destinationCoords[1]+","+destinationCoords[0]

+"?overview=full&geometries=geojson";



const response=await fetch(url);

const data=await response.json();



const coordinates=data.routes[0].geometry.coordinates.map(

p=>[p[1],p[0]]

);



if(routeLine){

map.removeLayer(routeLine);

}



routeLine=L.polyline(

coordinates,

{

color:"#d71920",

weight:6

}

).addTo(map);



map.fitBounds(routeLine.getBounds());



}

</script>


</body>
</html>
"""
