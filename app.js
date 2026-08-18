const API = "";


const map = L.map("map").setView(
    [1.3733, 32.2903],
    7
);


L.tileLayer(
"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
{
    maxZoom:19
}
).addTo(map);



async function searchAddress(){

    let query =
    document.getElementById("searchBox").value;


    let response =
    await fetch(
        `${API}/search?q=${query}`
    );


    let results =
    await response.json();


    console.log(results);


    results.forEach(place=>{


        let latitude =
        place[12];


        let longitude =
        place[13];


        L.marker(
            [
                latitude,
                longitude
            ]
        )
        .addTo(map)
        .bindPopup(
        `
        <b>${place[1]}</b><br>
        Address:<br>
        ${place[3]}<br>
        ZIP: ${place[8]}
        `
        );


    });


    if(results.length > 0){

        map.setView(
            [
                results[0][12],
                results[0][13]
            ],
            16
        );

    }

}
