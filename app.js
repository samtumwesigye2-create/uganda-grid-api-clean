let addresses = [];

fetch("entebbe_database_import.csv")
  .then(response => response.text())
  .then(csv => {
      console.log("Address database loaded");
      console.log(csv.slice(0,500));
  })
  .catch(error => {
      console.error("Database loading failed:", error);
  });
// Uganda National Address Finder
// Clean frontend version

let map;
let marker = null;
let currentLocation = null;

const API =
  "https://uganda-grid-api-clean-production.up.railway.app";

function initMap() {

  map = new maplibregl.Map({
    container: "map",
    style:
      "https://demotiles.maplibre.org/style.json",
    center: [32.4216234, 0.1491144],
    zoom: 16
  });

  map.addControl(
    new maplibregl.NavigationControl()
  );
}


async function searchAddress(){

  const query =
    document.getElementById("searchInput").value.trim();

  if(!query){
    alert("Enter Grid ID or address");
    return;
  }


  try {

    const response =
      await fetch(
        `${API}/address/${query}`
      );


    if(!response.ok){
      throw new Error("Address not found");
    }


    const data =
      await response.json();


    currentLocation = data;


    showResult(data);

    showMarker(
      Number(data.longitude),
      Number(data.latitude)
    );


  } catch(error){

    alert(error.message);

  }

}



function showResult(record){

 const results =
 document.getElementById("results");


 results.innerHTML = `

 <div class="result-card">

 <h2>
 ${record.address}
 </h2>

 <p>
 <b>Grid ID:</b>
 ${record.grid_id}
 </p>


 <p>
 <b>Building ID:</b>
 ${record.building_id}
 </p>


 <p>
 <b>Coordinates:</b>
 ${record.latitude},
 ${record.longitude}
 </p>


 <button id="navigateButton">
 🚗 Navigate Here
 </button>


 </div>

 `;


 document
 .getElementById("navigateButton")
 .onclick = function(){

    openNavigation(
      record.latitude,
      record.longitude
    );

 };


}



function showMarker(lng,lat){

 if(marker){

   marker
   .setLngLat([lng,lat]);

 }
 else{

 marker =
 new maplibregl.Marker()
 .setLngLat([lng,lat])
 .addTo(map);

 }


 map.flyTo({

 center:[lng,lat],
 zoom:18

 });


}



function openNavigation(lat,lng){

 const url =
 `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;


 window.open(url,"_blank");

}



document.addEventListener(
"DOMContentLoaded",
()=>{


 initMap();


 document
 .getElementById("searchButton")
 .addEventListener(
 "click",
 searchAddress
 );


 document
 .getElementById("searchInput")
 .addEventListener(
 "keydown",
 function(e){

 if(e.key==="Enter"){
 searchAddress();
 }

 });


});
