const API = "https://uganda-grid-api-clean-production.up.railway.app";

async function searchAddress() {

    const query = document.getElementById("searchBox").value;

    const url = `${API}/search?q=${encodeURIComponent(query)}`;

    console.log("Searching:", url);

    const response = await fetch(url);

    const data = await response.json();

    console.log(data);

    const table = document.getElementById("results");

    table.innerHTML = "";

    if (!data.results || data.results.length === 0) {
        table.innerHTML = `
        <tr>
            <td colspan="3">No results found</td>
        </tr>`;
        return;
    }

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
