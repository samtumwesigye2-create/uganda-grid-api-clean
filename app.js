let map;
let addresses = [];
let selectedLocation = null;

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

    const rows = csv.trim().split("\n");
    const headers = rows[0].split(",");

    addresses = rows.slice(1).map(row => {

        const values = row.split(",");

        let item = {};

        headers.forEach((header, index)=>{
            item[header.trim()] = values[index];
        });

        return item;

    });

    console.log("Loaded addresses:", addresses.length);

})
.catch(error=>{
    console.error("CSV loading error:", error);
});


// Search button
document.querySelector("#findAddress")
.addEventListener("click", ()=>{

    const input = document.querySelector("#addressInput")
    .value
    .toLowerCase()
    .trim();


    const result = addresses.find(item=>{

        return Object.values(item)
        .join(" ")
        .toLowerCase()
        .includes(input);

    });


    if(!result){

        alert("Address not found");
        return;

    }


    console.log(result);


    let lat =
    result.lat ||
    result.latitude ||
    result.Latitude;


    let lng =
    result.lng ||
    result.longitude ||
    result.Longitude;


    if(!lat || !lng){

        alert("Address found but coordinates missing");
        return;

    }


    selectedLocation = [
        Number(lng),
        Number(lat)
    ];


    map.flyTo({
        center:selectedLocation,
        zoom:18
    });


    new maplibregl.Marker()
    .setLngLat(selectedLocation)
    .addTo(map);


});
