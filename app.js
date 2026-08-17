let map;
let addresses = [];
let selectedDestination = null;
let destinationMarker = null;
let userMarker = null;


// MAP INITIALIZATION

map = new maplibregl.Map({
    container: "map",
    style: "https://demotiles.maplibre.org/style.json",
    center: [32.46, 0.05],
    zoom: 12
});

map.addControl(new maplibregl.NavigationControl());


// LOAD ADDRESS DATABASE

fetch("entebbe_database_import.csv")
.then(response => response.text())
.then(data => {

    const rows = data.trim().split(/\r?\n/);

    const headers = rows[0]
        .split(",")
        .map(x => x.trim());


    addresses = rows.slice(1).map(row => {

        const values = row.split(",");

        let item = {};

        headers.forEach((header,index)=>{

            item[header] = values[index] || "";

        });

        return item;

    });


    const message =
    document.getElementById("message");


    if(message){

        message.innerHTML =
        "Loaded " +
        addresses.length +
        " addresses";

    }


})
.catch(error=>{

    console.log(
        "CSV error:",
        error
    );

});



// SEARCH ADDRESS

function searchAddress(){

    const input =
    document.getElementById("searchInput");


    if(!input){

        return;

    }


    const query =
    input.value
    .toLowerCase()
    .trim();


    const result =
    addresses.find(item=>{

        return JSON.stringify(item)
        .toLowerCase()
        .includes(query);

    });


    if(!result){

        alert(
        "Address not found"
        );

        return;

    }


    const lat =
    Number(result.latitude);


    const lng =
    Number(result.longitude);



    selectedDestination = {

        latitude: lat,
        longitude: lng

    };



    if(destinationMarker){

        destinationMarker.remove();

    }



    destinationMarker =
    new maplibregl.Marker({

        color:"#ff0000"

    })

    .setLngLat([lng,lat])

    .addTo(map);



    map.flyTo({

        center:[lng,lat],

        zoom:18

    });



    const results =
    document.getElementById("results");


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


        <button onclick="startRoute()">

        🚗 Navigate Here

        </button>


        </div>

        `;

    }


}
// START NAVIGATION

function startRoute(){

    if(!selectedDestination){

        alert(
        "Please select an address first"
        );

        return;

    }



    navigator.geolocation.getCurrentPosition(

    function(position){


        const startLat =
        position.coords.latitude;


        const startLng =
        position.coords.longitude;



        const endLat =
        selectedDestination.latitude;


        const endLng =
        selectedDestination.longitude;



        const routeURL =

        "https://router.project-osrm.org/route/v1/driving/" +

        startLng + "," + startLat +

        ";" +

        endLng + "," + endLat +

        "?overview=full&geometries=geojson";



        fetch(routeURL)

        .then(response=>response.json())

        .then(data=>{


            if(!data.routes || !data.routes.length){

                alert(
                "No route found"
                );

                return;

            }



            const route =
            data.routes[0].geometry;



            if(map.getLayer("route")){

                map.removeLayer("route");

            }


            if(map.getSource("route")){

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

                    "line-width":6,

                    "line-color":"#0066ff"

                }

            });



            const km =

            (
            data.routes[0].distance / 1000
            )
            .toFixed(1);



            const message =
            document.getElementById("routeMessage");


            if(message){

                message.innerHTML =
                "Distance: "
                + km
                + " km";

            }



            map.fitBounds(

                [

                [startLng,startLat],

                [endLng,endLat]

                ],

                {

                padding:80

                }

            );


        })


        .catch(error=>{

            console.log(error);

            alert(
            "Routing failed"
            );

        });



    },


    function(){

        alert(
        "GPS permission required"
        );

    },


    {

        enableHighAccuracy:true

    });


}




// SHOW CURRENT LOCATION

function startNavigation(){


    navigator.geolocation.watchPosition(

    function(position){


        const lat =
        position.coords.latitude;


        const lng =
        position.coords.longitude;



        if(!userMarker){


            userMarker =
            new maplibregl.Marker({

                color:"#0066ff"

            })

            .setLngLat([lng,lat])

            .addTo(map);


        }

        else{


            userMarker
            .setLngLat([lng,lat]);


        }


    });


}



// CONNECT BUTTONS

window.searchAddress =
searchAddress;


window.startRoute =
startRoute;


window.startNavigation =
startNavigation;



document.addEventListener(

"DOMContentLoaded",

function(){


const searchButton =
document.getElementById(
"searchButton"
);


if(searchButton){

searchButton.onclick =
searchAddress;

}


const navButton =
document.getElementById(
"navigationButton"
);


if(navButton){

navButton.onclick =
startNavigation;

}


});
