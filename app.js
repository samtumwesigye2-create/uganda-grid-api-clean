let map;
let addresses = [];
let marker = null;
let userMarker = null;
let selectedDestination = null;

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
.then(csv => {

    const rows = csv.trim().split(/\r?\n/);

    const headers = rows[0]
        .split(",")
        .map(h => h.trim());


    addresses = rows.slice(1)
    .map(row => {

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
        "Database loaded: "
        + addresses.length
        + " addresses";

    }


})
.catch(error=>{

    console.error(
        "CSV loading error:",
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



    selectedDestination = {

        latitude: lat,
        longitude: lng

    };



    if(marker){

        marker.remove();

    }



    marker =
    new maplibregl.Marker()

    .setLngLat([
        lng,
        lat
    ])

    .addTo(map);



    map.flyTo({

        center:[
            lng,
            lat
        ],

        zoom:18

    });



    if(results){

        results.innerHTML = `

        <div class="result-card">

        <h3>
        ${result.address || "Address found"}
        </h3>


        <p>
        Building ID:
        ${result.building_id || ""}
        </p>


        <p>
        ZIP:
        ${result.zip_code || ""}
        </p>


        <button onclick="
        startRoute()
        ">
        🚗 Navigate Here
        </button>


        </div>

        `;

    }

}



// GET USER LOCATION

function startNavigation(){


    navigator.geolocation.watchPosition(

        position=>{


            const lat =
            position.coords.latitude;


            const lng =
            position.coords.longitude;



            if(!userMarker){


                userMarker =
                new maplibregl.Marker({

                    color:"#0066ff"

                })

                .setLngLat([
                    lng,
                    lat
                ])

                .addTo(map);


            }

            else{


                userMarker
                .setLngLat([
                    lng,
                    lat
                ]);

            }


        },


        error=>{

            console.log(error);

        },


        {

            enableHighAccuracy:true

        }

    );

}
// CREATE ROUTE FROM CURRENT LOCATION TO DESTINATION

function startRoute(){


    if(!selectedDestination){

        alert(
        "Please select an address first"
        );

        return;

    }



    navigator.geolocation.getCurrentPosition(

        position=>{


            const startLat =
            position.coords.latitude;


            const startLng =
            position.coords.longitude;



            const endLat =
            selectedDestination.latitude;


            const endLng =
            selectedDestination.longitude;



            const url =

            "https://router.project-osrm.org/route/v1/driving/" +

            startLng + "," +
            startLat +

            ";" +

            endLng + "," +
            endLat +

            "?overview=full&geometries=geojson";



            fetch(url)

            .then(response=>response.json())

            .then(data=>{


                const route =
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


                        "line-width":6


                    }


                });



                const distance =

                (
                data.routes[0].distance / 1000
                )

                .toFixed(1);



                const message =

                document.getElementById(
                    "routeMessage"
                );


                if(message){


                    message.innerHTML =

                    "Distance: "
                    + distance
                    + " km";


                }



            })

            .catch(error=>{


                console.log(
                "Route error:",
                error
                );


            });



        },


        error=>{


            alert(
            "Allow GPS location to navigate"
            );


        },


        {


            enableHighAccuracy:true


        }

    );


}



// CONNECT BUTTONS WHEN PAGE LOADS

document.addEventListener(
"DOMContentLoaded",

()=>{


    const searchButton =

    document.getElementById(
        "searchButton"
    );


    if(searchButton){


        searchButton.onclick =
        searchAddress;


    }



    const navigationButton =

    document.getElementById(
        "navigationButton"
    );


    if(navigationButton){


        navigationButton.onclick =
        startNavigation;


    }



});



// MAKE FUNCTIONS AVAILABLE

window.searchAddress =
searchAddress;


window.startNavigation =
startNavigation;


window.startRoute =
startRoute;
