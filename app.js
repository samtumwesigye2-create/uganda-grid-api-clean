let map;
let addresses = [];
let marker = null;
let userMarker = null;

map = new maplibregl.Map({
    container: "map",
    style: "https://demotiles.maplibre.org/style.json",
    center: [32.46, 0.05],
    zoom: 12
});

map.addControl(new maplibregl.NavigationControl());


// Load Entebbe address database

fetch("entebbe_database_import.csv")
.then(response => response.text())
.then(csv => {

    const rows = csv.trim().split("\n");

    const headers = rows[0]
        .split(",")
        .map(h => h.trim());

    addresses = rows.slice(1).map(row => {

        const values = row.split(",");

        let obj = {};

        headers.forEach((header,index)=>{
            obj[header] = values[index] || "";
        });

        return obj;

    });


    const message = document.getElementById("message");

    if(message){
        message.innerHTML =
        "Database loaded: " + addresses.length + " addresses";
    }


})
.catch(error=>{

    console.error(error);

});


// Search addresses

function searchAddress(){

    const input =
    document.getElementById("searchInput");


    if(!input){
        return;
    }


    const query =
    input.value.toLowerCase().trim();


    const result =
    addresses.find(address=>{

        return JSON.stringify(address)
        .toLowerCase()
        .includes(query);

    });


    const results =
    document.getElementById("results");


    if(!result){

        if(results){
            results.innerHTML =
            "Address not found";
        }

        return;
    }


    const lat =
    Number(result.latitude);


    const lng =
    Number(result.longitude);


    if(marker){

        marker.remove();

    }


    marker =
    new maplibregl.Marker()
    .setLngLat([lng,lat])
    .addTo(map);


    map.flyTo({

        center:[lng,lat],
        zoom:18

    });


    if(results){

        results.innerHTML = `

        <div class="result-card">

        <h3>
        ${result.address}
        </h3>

        <p>
        Building ID:
        ${result.building_id || ""}
        </p>

        <p>
        ZIP:
        ${result.zip_code || ""}
        </p>

        <button onclick="navigateToAddress(${lat},${lng})">
        🚗 Navigate Here
        </button>

        </div>

        `;

    }

}
