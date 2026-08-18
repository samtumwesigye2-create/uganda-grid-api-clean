const API =
"https://YOUR-API-URL.com";


let latitude = null;
let longitude = null;


let map = L.map('map').setView(
[0.3476,32.5825],
7
);


L.tileLayer(
'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
{
maxZoom:19
}
).addTo(map);


let marker;



async function searchAddress(){


let query =
document.getElementById("searchBox").value;


let response =
await fetch(
`${API}/search?q=${query}`
);


let data =
await response.json();



let table =
document.getElementById("results");


table.innerHTML="";



data.results.forEach(place=>{


latitude =
place.latitude;


longitude =
place.longitude;



table.innerHTML += `

<tr>

<td>${place.grid_id || ""}</td>

<td>${place.street || ""}</td>

<td>${place.address || ""}</td>

</tr>

`;



if(marker){

map.removeLayer(marker);

}



marker =
L.marker(
[
latitude,
longitude
]
)
.addTo(map)
.bindPopup(
place.address
)
.openPopup();



map.setView(
[
latitude,
longitude
],
17
);



});

}



function navigate(){


if(!latitude || !longitude){

alert(
"Search a location first"
);

return;

}


window.open(

`https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}`

);


}
