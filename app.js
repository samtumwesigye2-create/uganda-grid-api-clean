let map;
let addresses = [];
let selectedAddress = null;
let userLocation = null;
let userMarker = null;
let destinationMarker = null;


// ----------------------------
// CREATE MAP
// ----------------------------

map = new maplibregl.Map({

    container: "map",

    style:
    "https://demotiles.maplibre.org/style.json",

    center:
    [32.46, 0.05],

    zoom: 12

});


map.addControl(
    new maplibregl.NavigationControl()
);


// ----------------------------
// LOAD ADDRESS DATABASE
// ----------------------------


fetch("entebbe_database_import.csv")

.then(response => response.text())

.then(csv => {


    addresses = parseCSV(csv);


    console.log(
        "Loaded",
        addresses.length,
        "addresses"
    );


    const status =
    document.getElementById("message");


    if(status){

        status.innerHTML =
        "Database loaded: "
        + addresses.length
        + " addresses";

    }


})

.catch(error => {

    console.log(error);

    alert(
    "Database failed to load"
    );

});



// ----------------------------
// CSV READER
// ----------------------------


function parseCSV(text){


    const rows =
    text.trim().split("\n");


    const headers =
    rows[0]
    .split(",")
    .map(h=>h.trim());


    let result=[];


    for(let i=1;i<rows.length;i++){


        let values =
        rows[i].split(",");


        let item={};


        headers.forEach(
        (h,index)=>{


            item[h]=
            values[index]
            ?
            values[index].trim()
            :
            "";

        });


        result.push(item);


    }


    return result;


}




// ----------------------------
// SEARCH ADDRESS
// ----------------------------


function searchAddress(){


    const input =
    document.getElementById(
    "addressInput"
    );


    if(!input){
        return;
    }


    const query =
    input.value
    .toLowerCase()
    .trim();



    let found =
    addresses.find(item=>{


        let text =
        (
        item.address
        +" "
        +item.building_id
        +" "
        +item.grid_id
        +" "
        +item.zip
        )
        .toLowerCase();



        return text.includes(query);


    });



    if(!found){

        alert(
        "Address not found"
        );

        return;

    }



    selectedAddress = found;



    showAddress(found);



}



// ----------------------------
// SHOW ADDRESS RESULT
// ----------------------------


function showAddress(item){


    const lat =
    Number(
    item.latitude
    );


    const lng =
    Number(
    item.longitude
    );



    if(isNaN(lat)||isNaN(lng)){


        alert(
        "Coordinates missing"
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
    [lng,lat]
    )

    .addTo(map);



    map.flyTo({

        center:
        [lng,lat],

        zoom:17

    });



    const box =
    document.getElementById(
    "result"
    );


    if(box){

        box.innerHTML =

        `
        <h2>${item.address}</h2>

        <p>
        Building ID:
        ${item.building_id}
        </p>

        <p>
        ZIP:
        ${item.zip}
        </p>

        <button onclick="startNavigation()">
        🚗 Navigate Here
        </button>

        `;

    }


}


// ----------------------------
// GPS START
// ----------------------------


function startNavigation(){


    if(!selectedAddress){

        alert(
        "Choose an address first"
        );

        return;

    }



    if(!navigator.geolocation){


        alert(
        "GPS not supported"
        );

        return;

    }



    navigator.geolocation.getCurrentPosition(

    position=>{


        userLocation={


            latitude:
            position.coords.latitude,


            longitude:
            position.coords.longitude

        };



        showUser();



        createRoute();


    },


    error=>{


        alert(
        "GPS permission required"
        );


    },


    {

        enableHighAccuracy:true

    }


    );


}
// ----------------------------
// SHOW USER LOCATION
// ----------------------------

function showUser(){


    const lng =
    userLocation.longitude;


    const lat =
    userLocation.latitude;



    if(userMarker){


        userMarker
        .setLngLat(
        [lng,lat]
        );


    }

    else{


        userMarker =
        new maplibregl.Marker({

            color:"blue"

        })

        .setLngLat(
        [lng,lat]
        )

        .addTo(map);


    }



    map.flyTo({

        center:
        [lng,lat],

        zoom:16

    });


}




// ----------------------------
// CREATE ROUTE
// ----------------------------


async function createRoute(){


    if(!selectedAddress){

        alert(
        "No destination selected"
        );

        return;

    }



    const startLng =
    userLocation.longitude;


    const startLat =
    userLocation.latitude;



    const endLng =
    Number(
    selectedAddress.longitude
    );


    const endLat =
    Number(
    selectedAddress.latitude
    );



    if(
    isNaN(startLng) ||
    isNaN(startLat) ||
    isNaN(endLng) ||
    isNaN(endLat)
    ){

        alert(
        "Invalid coordinates"
        );

        return;

    }



    const url =

    "https://router.project-osrm.org/route/v1/driving/"
    +

    startLng
    + ","
    + startLat

    + ";"

    +

    endLng
    + ","
    + endLat

    +

    "?overview=full&geometries=geojson";




    try{


        const response =
        await fetch(url);



        const data =
        await response.json();




        if(
        !data.routes ||
        data.routes.length===0
        ){

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
        data.routes[0].distance
        /
        1000
        )

        .toFixed(2)

        +

        " km"

        );



    }


    catch(error){


        console.log(error);


        alert(
        "Routing service unavailable"
        );


    }



}




// ----------------------------
// DRAW ROUTE ON MAP
// ----------------------------


function drawRoute(route){



    if(
    map.getSource("route")
    ){


        map.removeLayer(
        "route"
        );


        map.removeSource(
        "route"
        );


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





// ----------------------------
// BUTTON CONNECTIONS
// ----------------------------


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




const navButton =
document.getElementById(
"navigateButton"
);



if(navButton){


navButton.onclick =
startNavigation;


}




const input =
document.getElementById(
"addressInput"
);



if(input){


input.addEventListener(

"keydown",

event=>{


if(event.key==="Enter"){

searchAddress();

}


}


);


}



});
