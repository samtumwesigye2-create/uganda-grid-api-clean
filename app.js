let map;
let marker;


// Your live Uganda Grid API
const API_URL = "https://ugrid-api-clean.onrender.com";


// Create map
map = new maplibregl.Map({
    container: "map",
    style: "https://demotiles.maplibre.org/style.json",
    center: [32.46, 0.05],
    zoom: 12
});


map.addControl(
    new maplibregl.NavigationControl()
);



// Search address
async function searchAddress() {

    const input = document
        .getElementById("addressInput")
        .value
        .trim();


    if (!input) {
        alert("Enter an address");
        return;
    }


    try {

        const response = await fetch(
            `${API_URL}/search?query=${encodeURIComponent(input)}`
        );


        if (!response.ok) {

            throw new Error("Search failed");

        }


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



        alert(
            "Found:\n\n" +
            (result.address || "") +
            "\nBuilding ID: " +
            (result.building_id || "")
        );


    } catch(error) {

        console.error(error);

        alert(
            "Could not connect to Uganda Grid API"
        );

    }

}



// Connect button

document
.getElementById("findAddress")
.addEventListener(
    "click",
    searchAddress
);
