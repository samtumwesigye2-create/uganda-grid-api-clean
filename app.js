let destination = null;
let userLocation = null;

let map = L.map("map").setView([0.3476, 32.5825], 13);

L.tileLayer(
"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
{
 maxZoom:19
}
).addTo(map);


let marker;


async function searchAddress(){

let query=document.getElementById("searchBox").value;

let response=await fetch(
"https://nominatim.openstreetmap.org/search?format=json&q="
+query
);

let data=await response.json();


if(data.length){

let lat=data[0].lat;
let lon=data[0].lon;


destination={
lat:lat,
lon:lon
};


map.setView(
[lat,lon],
15
);


if(marker){
map.removeLayer(marker);
}


marker=L.marker([lat,lon])
.addTo(map)
.bindPopup(query)
.openPopup();


document.getElementById("results").innerHTML=
`
<tr>
<td>${lat}</td>
<td>${lon}</td>
<td>${query}</td>
</tr>
`;

}

}




function getLocation(){

navigator.geolocation.getCurrentPosition(

function(position){

userLocation={
lat:position.coords.latitude,
lon:position.coords.longitude
};


L.marker([
userLocation.lat,
userLocation.lon
])
.addTo(map)
.bindPopup("You are here")
.openPopup();


}

);

}




function getRoute(){

if(!destination || !userLocation){

alert("Search destination and get your location first");
return;

}


let url=
"https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route="
+
userLocation.lat+","+userLocation.lon
+
";"
+
destination.lat+","+destination.lon;


window.open(url,"_blank");


}
function navigate(){

  let address = document.querySelector("#searchBox").value;

  let url = "https://www.google.com/maps/search/?api=1&query=" 
            + encodeURIComponent(address);

  window.open(url, "_blank");
}
