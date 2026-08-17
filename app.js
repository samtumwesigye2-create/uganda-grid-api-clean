let map;
let addresses = [];
let marker;


// Create map
map = new maplibregl.Map({
    container: "map",
    style: "https://demotiles.maplibre.org/style.json",
    center: [32.46, 0.05],
    zoom: 12
});

map.addControl(new maplibregl.NavigationControl());


// Load Uganda address database
fetch("entebbe_database_import.csv")
.then(response => response.text())
.then(csv => {

    const lines = csv.split(/\r?\n/);

    const headers = lines[0]
        .split(",")
        .map(x => x.trim());


    addresses = lines.slice(1)
    .filter(line => line.trim() !== "")
    .map(line => {

        const values = line.split(",");

        let record = {};

        headers.forEach((header,index)=>{

            record[header] = values[index] || "";

        });

        return record;

    });


    console.log(
        "Loaded addresses:",
        addresses.length
    );

})
.catch(error => {

    console.error(
        "Database error:",
        error
    );

});



// Find Address button
document
.getElementById("findAddress")
.addEventListener("click", function(){


    const search =
    document
    .getElementById("addressInput")
    .value
    .toLowerCase()
    .trim();



    const result =
    addresses.find(item => {


        let searchable =

        (
        item.address +
        " " +
        item.building_id +
        " " +
        item.grid_id
        )
        .toLowerCase();


        return searchable.includes(search);

    });



    if(!result){

        alert("Address not found");

        return;

    }



    let lat =
    Number(result.latitude);


    let lng =
    Number(result.longitude);



    if(isNaN(lat) || isNaN(lng)){


        alert(
        "Address found but coordinates missing"
        );


        return;

    }



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


});
