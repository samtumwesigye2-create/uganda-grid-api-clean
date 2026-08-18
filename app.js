const API = "https://uganda-grid-api-clean-production.up.railway.app";


async function searchAddress(){

    let query = document.getElementById("searchBox").value;

    let response = await fetch(
        `${API}/search?q=${query}`
    );

    let data = await response.json();


    let table = document.getElementById("results");

    table.innerHTML = "";


    data.results.forEach(place => {

        table.innerHTML += `
        <tr>
            <td>${place.grid_id || ""}</td>
            <td>${place.street || ""}</td>
            <td>${place.address || ""}</td>
        </tr>
        `;

    });

}
