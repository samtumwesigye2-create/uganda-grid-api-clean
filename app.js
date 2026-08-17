// =====================================
// Uganda National Address Finder
// Complete app.js
// =====================================


let map;

let addresses = [];

let selectedAddress = null;

let userLocation = null;

let userMarker = null;

let destinationMarker = null;



// =====================================
// START MAP
// =====================================

map = new maplibregl.Map({

    container: "map",

    style:
    "https://demotiles.maplibre.org/style.json",

    center:
    [
        32.45,
        0.05
    ],

    zoom:12

});


map.addControl(
    new maplibregl.NavigationControl()
);



// =====================================
// LOAD CSV DATABASE
// =====================================

async function loadDatabase(){

try{


document.getElementById("status").innerHTML =
"Loading 27,829 addresses...";



"./entebbe_database.json?v=1"
);



if(!response.ok){

throw new Error(
"CSV not found: "
+
response.status
);

}



const csv =
await response.text();



console.log(
"CSV size:",
csv.length
);



addresses =
parseCSV(csv);



document.getElementById("status").innerHTML =

"Database loaded: "

+

addresses.length

+

" addresses";



console.log(
addresses
);



}

catch(error){


console.error(error);


document.getElementById("status").innerHTML =

"Database error: "

+

error.message;


}



}



// =====================================
// CSV PARSER
// =====================================

function parseCSV(text){


let rows=[];

let row=[];

let value="";

let quotes=false;



for(let i=0;i<text.length;i++){


let c=text[i];



if(c === '"'){

quotes=!quotes;

}


else if(c === "," && !quotes){

row.push(value);

value="";

}


else if(c === "\n" && !quotes){

row.push(value);

rows.push(row);

row=[];

value="";

}


else{

value+=c;

}



}



if(value){

row.push(value);

}



if(row.length){

rows.push(row);

}



let headers =
rows.shift();



return rows.map(r=>{


let obj={};



headers.forEach((h,i)=>{


obj[
h.trim()
]=
(r[i] || "")
.replace(/^"|"$/g,"")
.trim();



});



return obj;



});



}



// =====================================
// SEARCH ADDRESS
// =====================================

function searchAddress(){


let query =

document
.getElementById("addressInput")
.value
.toLowerCase()
.trim();



if(!query){

return;

}



let result =

addresses.find(item=>{


let text =

Object.values(item)

.join(" ")

.toLowerCase();



return text.includes(query);



});



if(!result){


document.getElementById("result").innerHTML =

"Address not found";


return;


}



selectedAddress=result;



let lat =
Number(result.latitude);



let lng =
Number(result.longitude);



showDestination(
lat,
lng
);



document.getElementById("result").innerHTML =

`

<h2>${result.address || "Address Found"}</h2>

<p>
Building ID:
${result.building_id || ""}
</p>

<p>
Grid ID:
${result.grid_id || ""}
</p>

<p>
Coordinates:
${lat}, ${lng}
</p>

`;



}



// =====================================
// SHOW DESTINATION
// =====================================

function showDestination(lat,lng){



if(destinationMarker){

destinationMarker.remove();

}



destinationMarker =

new maplibregl.Marker({

color:"red"

})

.setLngLat(
[
lng,
lat
]
)

.addTo(map);



map.flyTo({

center:
[
lng,
lat
],

zoom:17

});



}



// =====================================
// GPS
// =====================================

function getLocation(){


navigator.geolocation.getCurrentPosition(


position=>{


userLocation={

latitude:
position.coords.latitude,

longitude:
position.coords.longitude

};



showUser();



},



error=>{


alert(
"GPS permission required"
);


},



{

enableHighAccuracy:true

}



);



}



// =====================================
// SHOW USER
// =====================================

function showUser(){



let lat =
userLocation.latitude;


let lng =
userLocation.longitude;



if(userMarker){

userMarker.setLngLat(
[
lng,
lat
]
);


}

else{


userMarker =

new maplibregl.Marker({

color:"blue"

})

.setLngLat(
[
lng,
lat
]
)

.addTo(map);



}



}



// =====================================
// CREATE ROUTE
// =====================================

async function createRoute(){



if(!selectedAddress){

alert(
"Search an address first"
);

return;

}



if(!userLocation){

getLocation();

alert(
"GPS loading. Press Navigate again."
);

return;

}



let start =

userLocation.longitude

+

","

+

userLocation.latitude;



let end =

selectedAddress.longitude

+

","

+

selectedAddress.latitude;



let url =

"https://router.project-osrm.org/route/v1/driving/"

+

start

+

";"

+

end

+

"?overview=full&geometries=geojson";



let response =
await fetch(url);



let data =
await response.json();



if(!data.routes.length){

alert(
"No route found"
);

return;

}



drawRoute(
data.routes[0].geometry
);



alert(

"Distance: "

+

(
data.routes[0].distance / 1000
)

.toFixed(2)

+

" km"

);



}



// =====================================
// DRAW ROUTE
// =====================================

function drawRoute(geometry){



if(map.getLayer("route")){

map.removeLayer("route");

}



if(map.getSource("route")){

map.removeSource("route");

}



map.addSource(

"route",

{

type:"geojson",

data:{

type:"Feature",

geometry:geometry

}

}

);



map.addLayer({

id:"route",

type:"line",

source:"route",

paint:{

"line-width":6,

"line-opacity":0.8

}

});



}



// =====================================
// BUTTONS
// =====================================

document.addEventListener(
"DOMContentLoaded",

()=>{


document
.getElementById("searchButton")
.onclick =
searchAddress;



document
.getElementById("navigateButton")
.onclick =
createRoute;



loadDatabase();



}

);
