const API = "https://uganda-grid-api-clean-production.up.railway.app";

let map;
let marker;

async function searchAddress(){

    let query = document.getElementById("searchBox").value;

    let response = await fetch(
        `${API}/search?q=${query}`
    );

    let data = await response.json();

    let table = document.getElementById("results");

    table.innerHTML = "";

    if(data.results.length === 0){
        alert("No address found");
        return;
    }

    let place = data.results[0];


    table.innerHTML = `
    <tr>
        <td>${place.grid_id}</td>
        <td>${place.street}</td>
        <td>${place.address}</td>
    </tr>
    `;


    showMap(
        Number(place.latitude),
        Number(place.longitude),
        place.address
    );
}



function showMap(lat, lng, address){

    if(!map){

        map = L.map('map').setView(
            [lat,lng],
            16
        );


        L.tileLayer(
        'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
        ).addTo(map);


    }else{

        map.setView(
            [lat,lng],
            16
        );

    }


    if(marker){
        map.removeLayer(marker);
    }


    marker = L.marker(
        [lat,lng]
    ).addTo(map)
    .bindPopup(address)
    .openPopup();


    document.getElementById("navigate").onclick = function(){

        window.open(
        `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`
        );

    };

}
