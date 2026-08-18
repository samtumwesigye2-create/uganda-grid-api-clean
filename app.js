const API =
"https://uganda-grid-api-clean-production.up.railway.app";


let map;
let marker;



async function searchAddress(){


    const query =
    document.getElementById("searchBox").value;


    const response = await fetch(
        `${API}/search?q=${encodeURIComponent(query)}`
    );


    const data = await response.json();



    const table =
    document.getElementById("results");


    table.innerHTML = "";



    if(!data.results || data.results.length === 0){

        table.innerHTML =
        `
        <tr>
        <td colspan="3">
        No results found
        </td>
        </tr>
        `;

        return;

    }



    const place = data.results[0];



    table.innerHTML =
    `

    <tr>

    <td>
    ${place.grid_id || ""}
    </td>


    <td>
    ${place.street || ""}
    </td>


    <td>
    ${place.address || ""}
    </td>

    </tr>

    `;



    const lat =
    Number(place.latitude);


    const lon =
    Number(place.longitude);



    if(!map){


        map = L.map("map")
        .setView(
            [lat, lon],
            16
        );


        L.tileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution:
            "© OpenStreetMap"
        }
        ).addTo(map);


    } else {


        map.setView(
            [lat, lon],
            16
        );

    }



    if(marker){

        marker.remove();

    }



    marker =
    L.marker(
        [lat, lon]
    )
    .addTo(map)
    .bindPopup(
        place.address
    )
    .openPopup();


}
