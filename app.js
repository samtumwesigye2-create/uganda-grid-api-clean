const API = "https://uganda-grid-api-clean-production.up.railway.app";


async function searchAddress(){

    const query = document.getElementById("searchBox").value;

    const response = await fetch(
        `${API}/search?q=${encodeURIComponent(query)}`
    );

    const data = await response.json();


    const table = document.getElementById("results");

    table.innerHTML = "";


    data.results.forEach(place => {

        table.innerHTML += `
            <tr>
                <td>${place.grid_id || place.id || ""}</td>
                <td>${place.code || place.street || ""}</td>
                <td>${place.address || ""}</td>
            </tr>
        `;

    });

}
