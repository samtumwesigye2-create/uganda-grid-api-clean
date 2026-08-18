const API = "YOUR_RAILWAY_API_URL";


async function searchAddress(){

    let query = document.getElementById("searchBox").value;


    let response = await fetch(
        `${API}/search?q=${query}`
    );


    let data = await response.json();


    let results =
    document.getElementById("results");


    results.innerHTML = "";


    data.results.forEach(place => {

        results.innerHTML += `
        <tr>
            <td>${place.grid_id}</td>
            <td>${place.street}</td>
            <td>${place.address}</td>
        </tr>
        `;

    });

}
