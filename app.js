let map;

let addresses = [];

let selectedAddress = null;

let userLocation = null;

let userMarker = null;

let destinationMarker = null;



// -------------------------
// START MAP
// -------------------------

map = new maplibregl.Map({

    container: "map",

    style:
    "https://demotiles.maplibre.org/style.json",

    center:
    [32.45, 0.05],

    zoom: 12

});


map.addControl(
    new maplibregl.NavigationControl()
);




// -------------------------
// LOAD DATABASE
// -------------------------

fetch("./entebbe_database_import.csv")

.then(response => {


    if(!response.ok){

        throw new Error(
        "CSV not found"
        );

    }


    return response.text();


})


.then(csv => {


    addresses = parseCSV(csv);



    document.getElementById("status").innerHTML =

    "Database loaded: "

    +

    addresses.length

    +

    " addresses";


    console.log(
    "Loaded",
    addresses.length,
    "addresses"
    );


})


.catch(error => {


    console.log(error);


    document.getElementById("status").innerHTML =

    "Database loading failed";


});




// -------------------------
// CSV PARSER
// -------------------------

function parseCSV(text){


    const rows = [];

    let current = "";

    let insideQuotes = false;

    let row = [];



    for(let i=0;i<text.length;i++){


        let char=text[i];


        if(char === '"'){

            insideQuotes =
            !insideQuotes;

        }


        else if(
            char === "," &&
            !insideQuotes
        ){

            row.push(current);

            current="";

        }


        else if(
            char === "\n" &&
            !insideQuotes
        ){

            row.push(current);

            rows.push(row);

            row=[];

            current="";

        }


        else{

            current += char;

        }


    }



    if(current){

        row.push(current);

    }


    if(row.length){

        rows.push(row);

    }



    let headers =
    rows.shift();



    return rows.map(row=>{


        let obj={};


        headers.forEach(
        (header,index)=>{


            obj[
            header.trim()
            ] =
            row[index]
            ?
            row[index].trim()
            :
            "";


        });



        return obj;


    });



}

}


}


);


}



});
// -------------------------
// SEARCH ADDRESS
// -------------------------

function searchAddress(){


    let input =
    document.getElementById(
    "addressInput"
    );


    let query =
    input.value
    .toLowerCase()
    .trim();



    let result =
    addresses.find(item=>{


        let text =

        (

        item.grid_id

        +

        " "

        +

        item.building_id

        +

        " "

        +

        item.address

        +

        " "

        +

        item.street

        +

        " "

        +

        item.city

        )

        .toLowerCase();



        return text.includes(query);



    });



    if(!result){


        document.getElementById("result").innerHTML =

        "Address not found";


        return;


    }



    selectedAddress = result;



    let lat =
    Number(result.latitude);


    let lng =
    Number(result.longitude);



    if(isNaN(lat) || isNaN(lng)){


        alert(
        "Invalid coordinates"
        );

        return;


    }



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



    document.getElementById("result").innerHTML =


    `

    <h2>
    ${result.address || "Address Found"}
    </h2>


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



// -------------------------
// GPS LOCATION
// -------------------------

function getLocation(){


    navigator.geolocation.getCurrentPosition(


    function(position){


        userLocation = {


            latitude:
            position.coords.latitude,


            longitude:
            position.coords.longitude


        };



        showUserLocation();



    },


    function(){


        alert(
        "GPS permission required"
        );


    },


    {

        enableHighAccuracy:true

    }



    );

}



// -------------------------
// SHOW USER LOCATION
// -------------------------

function showUserLocation(){



    if(!userLocation){

        return;

    }



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



// -------------------------
// CREATE ROUTE
// -------------------------

async function createRoute(){


    if(!selectedAddress){


        alert(
        "Select an address first"
        );


        return;


    }



    if(!userLocation){


        getLocation();


        alert(
        "Getting GPS location. Press navigate again."
        );


        return;


    }



    let startLat =
    userLocation.latitude;


    let startLng =
    userLocation.longitude;



    let endLat =
    Number(selectedAddress.latitude);



    let endLng =
    Number(selectedAddress.longitude);



    let url =

    "https://router.project-osrm.org/route/v1/driving/"

    +

    startLng

    +

    ","

    +

    startLat

    +

    ";"

    +

    endLng

    +

    ","

    +

    endLat

    +

    "?overview=full&geometries=geojson";



    let response =
    await fetch(url);



    let data =
    await response.json();



    if(!data.routes || !data.routes.length){


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

// -------------------------
// DRAW ROUTE ON MAP
// -------------------------

function drawRoute(route){


    if(map.getSource("route")){


        if(map.getLayer("route")){

            map.removeLayer("route");

        }


        map.removeSource("route");


    }




    map.addSource(
    "route",
    {

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

            "line-opacity":0.8

        }

    });



}



// -------------------------
// BUTTON CONNECTIONS
// -------------------------

document
.addEventListener(
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




    const navigateButton =

    document.getElementById(
    "navigateButton"
    );


    if(navigateButton){

        navigateButton.onclick =

        function(){

            getLocation();

            setTimeout(
            createRoute,
            2000
            );

        };

    }



});



// -------------------------
// MAKE FUNCTIONS AVAILABLE
// -------------------------

window.searchAddress =
searchAddress;


window.getLocation =
getLocation;


window.createRoute =
createRoute;
