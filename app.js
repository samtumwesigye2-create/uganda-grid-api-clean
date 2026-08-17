const API =
"https://uganda-grid-api-clean.onrender.com";


const map = L.map("map").setView(
    [0.05,32.46],
    13
);


L.tileLayer(
"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
{
    maxZoom:19
}
).addTo(map);



let markers=[];



function addBuilding(record){

    let id = record[1];
    let address = record[3];
    let lat = record[10];
    let lon = record[11];


    if(lat && lon){

        let marker = L.marker(
            [lat,lon]
        ).addTo(map);


        marker.bindPopup(
        `
        <b>${id}</b><br>
        ${address}
        `
        );


        markers.push(marker);
    }

}



async function loadBuildings(){

    let response =
    await fetch(
    API+"/search?q=Entebbe"
    );


    let data =
    await response.json();


    data.forEach(addBuilding);


}



loadBuildings();



document
.getElementById("search")
.addEventListener(
"change",
async function(){

    let q=this.value;


    let response =
    await fetch(
    API+"/search?q="+q
    );


    let data =
    await response.json();


    markers.forEach(
        m=>map.removeLayer(m)
    );


    markers=[];


    data.forEach(addBuilding);


});
