let map;
let addresses = [];
let marker;
let userMarker;

// -------------------------
// CREATE MAP
// -------------------------

map = new maplibregl.Map({
    container: "map",
    style: "https://demotiles.maplibre.org/style.json",
    center: [32.46, 0.05],
    zoom: 12
});

map.addControl(new maplibregl.NavigationControl());


// -------------------------
// LOAD DATABASE
// -------------------------

fetch("entebbe_database_import.csv")
.then(response => response.text())
.then(csv => {

    let lines = csv.split(/\r?\n/);

    let headers = lines[0]
        .split(",")
        .map(x => x.trim());

    addresses = lines.slice(1)
    .filter(x => x.trim() !== "")
    .map(line => {

        let values = line.split(",");

        let obj = {};

        headers.forEach((header,index)=>{
            obj[header] = values[index] || "";
        });

        return obj;
    });


    let message = document.getElementById("message");

    if(message){
        message.innerHTML =
        "Database loaded: " + addresses.length + " addresses";
    }

})
.catch(error=>{
    console.log(error);
});


// -------------------------
// SEARCH ADDRESS
// -------------------------

function searchAddress(){

    let input = document.getElementById("searchInput");

    if(!input) return;


    let query = input.value
    .toLowerCase()
    .trim();


    let result = addresses.find(item=>{

        return JSON.stringify(item)
        .toLowerCase()
        .includes(query);

    });


    let resultsBox =
    document.getElementById("results");


    if(!result){

        if(resultsBox)
        resultsBox.innerHTML =
        "Address not found";

        return;
    }


    let lat = Number(result.latitude);
    let lng = Number(result.longitude);



    if(marker){
        marker.remove();
    }


    marker = new maplibregl.Marker()
    .setLngLat([lng,lat])
    .addTo(map);


    map.flyTo({

        center:[lng,lat],
        zoom:18

    });



    if(resultsBox){

        resultsBox.innerHTML = `

        <div class="result-card">

        <h2>
        ${result.address || "Address found"}
        </h2>

        <p>
        Grid ID:
        ${result.grid_id || ""}
        </p>

        <p>
        Building ID:
        ${result.building_id || ""}
        </p>

        <p>
        Coordinates:
        ${lat}, ${lng}
        </p>


        <button onclick="
        startRoute(${lat},${lng})
        ">

        🚗 Navigate Here

        </button>

        </div>

        `;

    }

}


// -------------------------
// START ROUTE
// -------------------------

function startRoute(destinationLat,destinationLng){


navigator.geolocation.getCurrentPosition(

(position)=>{


let startLat =
position.coords.latitude;


let startLng =
position.coords.longitude;



let url =

"https://router.project-osrm.org/route/v1/driving/" +

startLng + "," +
startLat +

";" +

destinationLng + "," +
destinationLat +

"?overview=full&geometries=geojson";



fetch(url)

.then(response=>response.json())

.then(data=>{


let route =
data.routes[0].geometry;



if(map.getSource("route")){

map.removeLayer("route");

map.removeSource("route");

}



map.addSource("route",{

type:"geojson",

data:{

type:"Feature",

geometry:route

}

});



map.addLayer({

id:"route",

type:"line",

source:"route",

paint:{

"line-width":5

}

});



let distance =
(data.routes[0].distance/1000)
.toFixed(1);



let routeMessage =
document.getElementById("routeMessage");


if(routeMessage){

routeMessage.innerHTML =
"Distance: "
+ distance
+ " km";

}


});


},

(error)=>{

alert(
"Please allow GPS location"
);

}

);


}


// -------------------------
// LIVE GPS
// -------------------------

function startNavigation(){


navigator.geolocation.watchPosition(

(position)=>{


let lat =
position.coords.latitude;


let lng =
position.coords.longitude;



if(!userMarker){


userMarker =
new maplibregl.Marker({

color:"#007AFF"

})

.setLngLat([lng,lat])

.addTo(map);


}

else{


userMarker.setLngLat(
[lng,lat]
);


}



},

(error)=>{

console.log(error);

}

);


}



// -------------------------
// BUTTON CONNECTIONS
// -------------------------

window.searchAddress =
searchAddress;


window.startNavigation =
startNavigation;


window.startRoute =
startRoute;



document.addEventListener(
"DOMContentLoaded",

()=>{


let button =
document.getElementById("searchButton");


if(button){

button.onclick =
searchAddress;

}



let nav =
document.getElementById("navigationButton");


if(nav){

nav.onclick =
startNavigation;

}



}

);
