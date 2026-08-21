window.onload = function(){

const map = L.map("map").setView(
    [1.3733,32.2903],
    7
);


L.tileLayer(
"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
{
maxZoom:19,
attribution:"© OpenStreetMap contributors"
}
).addTo(map);



const start =
document.getElementById("start");

const destination =
document.getElementById("destination");

const navigate =
document.getElementById("navigate");

const myLocation =
document.getElementById("myLocation");


const status =
document.getElementById("status");

const info =
document.getElementById("info");



let routeLine = null;

let userMarker = null;





const cities = [

["Kampala",0.3476,32.5825],
["Entebbe",0.0512,32.4637],
["Jinja",0.4479,33.2026],
["Mbarara",-0.6072,30.6545],
["Mbale",1.0821,34.1750],
["Gulu",2.7746,32.2990]

];



cities.forEach(city=>{


L.marker(
[
city[1],
city[2]
]
)

.addTo(map)

.bindPopup(city[0]);


});





function setStatus(text,type){

status.textContent=text;

status.className="status "+(type||"");


}



async function searchAddress(query){

const response =
await fetch(

"https://nominatim.openstreetmap.org/search?format=json&countrycodes=ug&q="
+
encodeURIComponent(query)

);


const data =
await response.json();


if(!data.length){

throw Error(
"Location not found"
);

}


return {

lat:Number(data[0].lat),

lon:Number(data[0].lon),

name:data[0].display_name

};


}
    function setupSearch(input){

let box =
document.createElement("div");

box.className="suggest";


input.parentNode.insertBefore(
box,
input.nextSibling
);



input.addEventListener(
"input",
async function(){


let q =
input.value.trim();



if(q.length < 3){

box.style.display="none";

return;

}



try{


const response =
await fetch(

"https://nominatim.openstreetmap.org/search?format=json&limit=5&countrycodes=ug&q="
+
encodeURIComponent(q)

);



const results =
await response.json();



box.innerHTML="";



results.forEach(place=>{


let item =
document.createElement("div");



item.textContent =
place.display_name;



item.style.padding="8px";

item.style.borderBottom=
"1px solid #ddd";

item.style.cursor=
"pointer";




item.onclick=function(){



input.value =
place.display_name;



input.dataset.lat =
place.lat;



input.dataset.lon =
place.lon;



box.style.display=
"none";



setStatus(
"✓ Location selected",
"ok"
);



};



box.appendChild(item);



});



box.style.display =
results.length
?
"block"
:
"none";



}

catch(error){

console.error(error);

box.style.display="none";

}



});


}




setupSearch(start);

setupSearch(destination);






async function getCoordinates(input){


if(
!input.dataset.lat ||
!input.dataset.lon
){

throw Error(
"Select a location from suggestions"
);

}



return {

lat:Number(input.dataset.lat),

lon:Number(input.dataset.lon)

};


}




async function getRoute(startPoint,endPoint){


const url =

"https://router.project-osrm.org/route/v1/driving/"

+

startPoint.lon

+

","

+

startPoint.lat

+

";"

+

endPoint.lon

+

","

+

endPoint.lat

+

"?overview=full&geometries=geojson";



const response =
await fetch(url);



const data =
await response.json();



if(
!data.routes ||
!data.routes.length
){

throw Error(
"No route found"
);

}



return data.routes[0];


}
    async function drawRoute(){


try{


const startPoint =
await getCoordinates(start);



const endPoint =
await getCoordinates(destination);



setStatus(
"Calculating route...",
""
);



const route =
await getRoute(
startPoint,
endPoint
);



const coordinates =
route.geometry.coordinates.map(
point=>[
point[1],
point[0]
]
);



if(routeLine){

map.removeLayer(routeLine);

}



routeLine =
L.polyline(

coordinates,

{

color:"#d71920",

weight:6,

smoothFactor:1

}

)

.addTo(map);




map.fitBounds(
routeLine.getBounds(),
{
padding:[30,30]
}
);



const km =
(route.distance / 1000)
.toFixed(1);



const minutes =
Math.round(
route.duration / 60
);



info.innerHTML =

"📍 Route: "

+

km

+

" km · "

+

minutes

+

" min";



setStatus(
"🧭 Navigation ready",
"ok"
);



}

catch(error){


console.error(error);



setStatus(
error.message,
"err"
);


}


}






navigate.onclick =
function(){

drawRoute();

};






myLocation.onclick =
function(){



if(!navigator.geolocation){

setStatus(
"Location unavailable",
"err"
);

return;

}



navigator.geolocation.getCurrentPosition(

function(position){



const lat =
position.coords.latitude;



const lon =
position.coords.longitude;



if(userMarker){

map.removeLayer(userMarker);

}



userMarker =
L.marker(
[
lat,
lon
]
)

.addTo(map)

.bindPopup(
"You are here"
)

.openPopup();



map.setView(
[
lat,
lon
],
15
);



setStatus(
"📍 Location found",
"ok"
);



},

function(){

setStatus(
"Unable to get location",
"err"
);


}

);


}





setTimeout(

function(){

map.invalidateSize();

},

1000
);



};

// Optional: Google Maps handoff

const googleButton =
document.getElementById("googleMaps");


if(googleButton){


googleButton.onclick=function(){


let destinationText =
destination.value;



if(!destinationText){

setStatus(
"Enter a destination first",
"err"
);

return;

}



window.open(

"https://www.google.com/maps/search/?api=1&query="
+
encodeURIComponent(destinationText),

"_blank"

);



};


}





// UGAMAP button

const ugamapButton =
document.getElementById("ugamaps");


if(ugamapButton){


ugamapButton.onclick=function(){


setStatus(
"🇺🇬 Uganda map mode active",
"ok"
);



map.invalidateSize();



};


}







// Keep map responsive after loading


window.addEventListener(
"resize",
function(){

map.invalidateSize();

}

);





};

// Final map refresh

setTimeout(function(){

    map.invalidateSize();

},1500);



// Confirm app loaded

setStatus(
    "🇺🇬 Uganda National Grid ready",
    "ok"
);



};
