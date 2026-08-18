const API = "https://uganda-grid-api-clean-production.up.railway.app";


async function searchAddress(){

    let query = document.getElementById("searchBox").value;


    try {

        let response = await fetch(
            `${API}/search?q=${encodeURIComponent(query)}`
        );


        let data = await response.json();


        console.log(data);


        let table = document.getElementById("results");

        table.innerHTML = "";


        data.results.forEach(place => {


            table.innerHTML += `

            <tr>

                <td>
                    ${place.grid_id || ""}
                </td>

                <td>
                    ${place.subcounty_code || place.street || ""}
                </td>

                <td>
                    ${place.address || ""}
                </td>

            </tr>

            `;

        });


    } catch(error){

        console.log(error);

        alert("API connection failed");

    }

}
