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

const mode =
document.getElementById("mode");

const status =
document.getElementById("status");

const info =
document.getElementById("info");

const myLocation =
document.getElementById("myLocation");



let routeLine = null;

let userMarker = null;




function setStatus(text,type=""){

status.textContent = text;

status.className =
"status " + type;

}




// -------------------------
// ADDRESS SEARCH
// -------------------------


function createSuggestionBox(input){

let box =
document.createElement("div");

box.className="suggest";


input.parentNode.insertBefore(
box,
input.nextSibling
);


return box;

}



const startBox =
createSuggestionBox(start);


const destinationBox =
createSuggestionBox(destination);





async function searchAddress(query){

const response =
await fetch(

"https://nominatim.openstreetmap.org/search?format=json&limit=5&countrycodes=ug&q="
+
encodeURIComponent(query)

);



const data =
await response.json();



return data;

}
    function showSuggestions(
input,
box,
results
){

box.innerHTML="";


if(!results.length){

box.style.display="none";

return;

}



results.forEach(place=>{


const item =
document.createElement("div");


item.textContent =
place.display_name;


item.style.padding="8px";

item.style.background="white";

item.style.borderBottom=
"1px solid #ddd";

item.style.cursor="pointer";



item.onclick=function(){



// KEEP FULL ADDRESS

input.value =
place.display_name;



// SAVE EXACT COORDINATES

input.dataset.lat =
place.lat;


input.dataset.lon =
place.lon;



input.dataset.address =
place.display_name;



box.style.display="none";



setStatus(
"✓ Address selected",
"ok"
);



};



box.appendChild(item);



});



box.style.display="block";



}





function activateSearch(input,box){


input.addEventListener(
"input",
async function(){



const q =
input.value.trim();



if(q.length < 3){

box.style.display="none";

return;

}



try{


const results =
await searchAddress(q);



showSuggestions(
input,
box,
results
);



}

catch(error){


console.error(error);


box.style.display="none";


}


});


}





activateSearch(
start,
startBox
);



activateSearch(
destination,
destinationBox
);






async function getCoordinates(input){


if(
input.dataset.lat &&
input.dataset.lon
){


return {

lat:Number(input.dataset.lat),

lon:Number(input.dataset.lon)

};


}



throw Error(
"Select an address from the suggestions"
);



}
    async function getRoute(startPoint,endPoint){


let profile = "driving";


if(mode.value === "walking"){

profile = "foot";

}


if(mode.value === "cycling"){

profile = "bike";

}





const url =

"https://router.project-osrm.org/route/v1/"
+
profile
+
"/"
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


const a =
await getCoordinates(start);



const b =
await getCoordinates(destination);



setStatus(
"Calculating route...",
""
);



const route =
await getRoute(a,b);




const points =
route.geometry.coordinates.map(
p=>[
p[1],
p[0]
]
);




if(routeLine){

map.removeLayer(routeLine);

}




routeLine =
L.polyline(

points,

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





info.innerHTML =

"📏 "
+
(route.distance/1000).toFixed(1)
+
" km · ⏱ "
+
Math.round(route.duration/60)
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
    navigate.onclick = function(){

drawRoute();

};





myLocation.onclick = function(){


if(!navigator.geolocation){


setStatus(
"Location not supported",
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
"📍 Current location found",
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



};






// CLOSE SUGGESTIONS WHEN CLICKING MAP


map.on(
"click",
function(){


startBox.style.display="none";

destinationBox.style.display="none";


}

);





// REFRESH MAP SIZE


setTimeout(

function(){

map.invalidateSize();

},

1000

);



};

// OPTIONAL GOOGLE MAPS BUTTON

const googleMaps =
document.getElementById("googleMaps");


if(googleMaps){


googleMaps.onclick=function(){


if(!destination.value){

setStatus(
"Enter a destination first",
"err"
);

return;

}



window.open(

"https://www.google.com/maps/search/?api=1&query="
+
encodeURIComponent(
destination.value
),

"_blank"

);



};



}





// OPTIONAL UGAMAP BUTTON

const ugamaps =
document.getElementById("ugamaps");



if(ugamaps){


ugamaps.onclick=function(){


setStatus(
"🇺🇬 Uganda map active",
"ok"
);



map.invalidateSize();



};


}





setStatus(
"🇺🇬 Uganda National Grid ready",
"ok"
);



};
