let map;
let marker;

const API_URL = "https://ugrid-api-clean.onrender.com";


// MAP
map = new maplibregl.Map({
    container: "map",
    style: "https://demotiles.maplibre.org/style.json",
    center: [32.46, 0.05],
    zoom: 12
});


map.addControl(
    new maplibregl.NavigationControl()
);


// SEARCH
async function searchAddress() {

    const input = document
        .getElementById("addressInput")
        .value
        .trim();


    if (!input) {
        alert("Enter Building ID or Address");
        return;
    }


    try {

        const response = await fetch(
            `${API_URL}/search?q=${encodeURIComponent(input)}`
        );


        const result = await response.json();


        console.log(result);


        if (!result || !result.latitude) {

            alert("Address not found");
            return;

        }


        const lat = Number(result.latitude);
        const lng = Number(result.longitude);



        if (marker) {
            marker.remove();
        }


        marker = new maplibregl.Marker()
            .setLngLat([lng, lat])
            .addTo(map);



        map.flyTo({

            center: [lng, lat],
            zoom: 18

        });



    } catch(error) {

        console.error(error);

        alert(
            "Cannot connect to Uganda Grid API"
        );

    }

}



// BUTTON
document
.getElementById("findAddress")
.addEventListener(
    "click",
    searchAddress
);
