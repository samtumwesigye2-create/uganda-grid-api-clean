let map;
let marker;

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


// Search function
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

        const url =
        `${API_URL}/search?q=${encodeURIComponent(input)}`;


        console.log("Searching:", url);


        const response = await fetch(url);


        if (!response.ok) {

            throw new Error(
                "API request failed"
            );

        }


        const data = await response.json();


        console.log("API result:", data);



        let result = data;


        // If API returns a list, use first result
        if (Array.isArray(data)) {

            if (data.length === 0) {

                alert("Address not found");
                return;

            }

            result = data[0];

        }



        const lat = Number(result.latitude);
        const lng = Number(result.longitude);



        if (
            Number.isNaN(lat) ||
            Number.isNaN(lng)
        ) {

            alert(
                "Address found but coordinates missing"
            );

            return;

        }



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
            "FOUND\n\n" +
            "Address: " +
            (result.address || "") +
            "\nBuilding ID: " +
            (result.building_id || "") +
            "\nGrid ID: " +
            (result.grid_id || "")
        );


    } catch(error) {

        console.error(error);

        alert(
            "Could not connect to Uganda Grid API"
        );

    }

}



// Button connection
document
.getElementById("findAddress")
.addEventListener(
    "click",
    searchAddress
);
