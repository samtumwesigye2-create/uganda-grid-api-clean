let map;
let addresses = [];
let marker;


// MAP
map = new maplibregl.Map({
    container: "map",
    style: "https://demotiles.maplibre.org/style.json",
    center: [32.46, 0.05],
    zoom: 12
});

map.addControl(new maplibregl.NavigationControl());


// LOAD DATABASE
fetch("entebbe_database_import.csv")
.then(response => response.text())
.then(csv => {

    const lines = csv.trim().split("\n");

    const headers = lines[0]
        .split(",")
        .map(h => h.trim());


    addresses = lines.slice(1).map(line => {

        const values = line.split(",");

        let obj = {};

        headers.forEach((header,index)=>{
            obj[header] = values[index];
        });

        return obj;

    });


    console.log(
        "DATABASE LOADED:",
        addresses.length,
        "records"
    );

})
.catch(error => {

    alert("Database failed to load");

    console.error(error);

});



// SEARCH
function searchAddress(){


    let query = document
        .getElementById("addressInput")
        .value
        .toLowerCase()
        .trim();



    if(!query){

        alert("Enter an address");

        return;
    }



    let result = addresses.find(record=>{


        return Object.values(record)
        .join(" ")
        .toLowerCase()
        .includes(query);


    });



    if(!result){

        alert(
          "Address not found"
        );

        return;

    }



    let latitude =
        Number(result.latitude);



    let longitude =
        Number(result.longitude);



    if(
        isNaN(latitude) ||
        isNaN(longitude)
    ){

        alert(
        "Address found but coordinates missing"
        );

        return;

    }



    if(marker){

        marker.remove();

    }



    marker = new maplibregl.Marker()
    .setLngLat([
        longitude,
        latitude
    ])
    .addTo(map);



    map.flyTo({

        center:[
            longitude,
            latitude
        ],

        zoom:18

    });



    alert(

        "FOUND:\n\n" +
        (result.address || "") +
        "\n\nBuilding ID: " +
        (result.building_id || "") +
        "\n\nGrid ID: " +
        (result.grid_id || "")

    );

}



// BUTTON CONNECTION

document
.getElementById("findAddress")
.addEventListener(
    "click",
    searchAddress
);
