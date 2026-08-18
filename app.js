const API = "https://uganda-grid-api-clean-production.up.railway.app";

async function searchAddress() {

    const query = document.getElementById("searchBox").value;

    const response = await fetch(
        `${API}/search?q=${encodeURIComponent(query)}`
    );

    const data = await response.json();

    const table = document.getElementById("results");

    table.innerHTML = "";

    data.results.forEach(place => {

        const row = `
        <tr>
            <td>${place.grid_id}</td>
            <td>${place.street}</td>
            <td>${place.address}</td>
        </tr>
        `;

        table.innerHTML += row;

    });

}
