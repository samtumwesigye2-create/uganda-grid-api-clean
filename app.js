const API =
  "https://uganda-grid-api-clean-production.up.railway.app";

const ROUTER =
  "https://router.project-osrm.org";

let map;
let marker = null;
let routeSource = null;


function initMap() {

  map = new maplibregl.Map({
    container: "map",
    style: "https://tiles.openfreemap.org/styles/liberty",
    center: [32.4216, 0.1491],
    zoom: 16
  });

  map.addControl(
    new maplibregl.NavigationControl()
  );

}


async function searchUgandaAddress(query) {

  const response = await fetch(
    API +
    "/search?q=" +
    encodeURIComponent(query)
  );

  if (!response.ok) {
    throw new Error("Search failed");
  }

  return await response.json();

}


function showLocation(record) {

  const lng =
    Number(record.longitude);

  const lat =
    Number(record.latitude);


  if (marker) {
    marker.remove();
  }


  marker =
    new maplibregl.Marker()
      .setLngLat([
        lng,
        lat
      ])
      .addTo(map);


  map.flyTo({

    center: [
      lng,
      lat
    ],

    zoom: 19,

    duration: 1500

  });


}


function displayResult(record) {

  const results =
    document.getElementById("results");


  results.innerHTML = `

  <div class="result-card">

    <h2>
      ${record.address}
    </h2>

    <p>
      Grid ID:
      ${record.grid_id}
    </p>

    <p>
      Building ID:
      ${record.building_id}
    </p>

    <p>
      Coordinates:
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

  const destination =
    document.querySelector(".result-card h2").innerText;

  document.getElementById("toInput").value =
    destination;

  document.getElementById("navigationTab").click();

};

      document.getElementById(
        "toInput"
      ).value =
        record.address;

    };


  showLocation(record);

}



async function findAddress(){

  const input =
    document.getElementById(
      "searchInput"
    );


  const message =
    document.getElementById(
      "message"
    );


  try {

    message.innerHTML =
      "Searching...";


    const data =
      await searchUgandaAddress(
        input.value
      );


    if(
      data.length === 0
    ){

      message.innerHTML =
        "No address found";

      return;

    }


    displayResult(
      data[0]
    );


    message.innerHTML =
      "Address found";


  }

  catch(error){

    console.error(error);

    message.innerHTML =
      "Search failed";

  }

}



async function findRoute(){

  const from =
    document.getElementById(
      "fromInput"
    ).value;


  const to =
    document.getElementById(
      "toInput"
    ).value;


  try {


    const startResults =
      await searchUgandaAddress(
        from
      );


    const endResults =
      await searchUgandaAddress(
        to
      );


    const start =
      startResults[0];


    const end =
      endResults[0];


    const url =
      ROUTER +
      "/route/v1/driving/" +

      start.longitude +
      "," +
      start.latitude +

      ";" +

      end.longitude +
      "," +
      end.latitude +

      "?overview=full&geometries=geojson";


    const response =
      await fetch(url);


    const data =
      await response.json();


    const route =
      data.routes[0];


    if(
      map.getSource("route")
    ){

      map.removeLayer("route");

      map.removeSource("route");

    }


    map.addSource(
      "route",
      {

        type:"geojson",

        data:{

          type:"Feature",

          geometry:
            route.geometry

        }

      }
    );


    map.addLayer({

      id:"route",

      type:"line",

      source:"route",

      paint:{

        "line-width":6

      }

    });


    document.getElementById(
      "routeInfo"
    ).innerHTML = `

    <h3>Driving Route</h3>

    Distance:
    ${(route.distance/1000).toFixed(2)}
    km

    <br>

    Time:
    ${(route.duration/60).toFixed(0)}
    minutes

    `;


  }

  catch(error){

    console.error(error);

    alert(
      "Route failed"
    );

  }

}



document.addEventListener(
"DOMContentLoaded",
function(){

  initMap();


  const searchButton =
    document.getElementById(
      "searchButton"
    );


  if(searchButton){

    searchButton.onclick =
      findAddress;

  }


  const routeButton =
    document.getElementById(
      "routeButton"
    );


  if(routeButton){

    routeButton.onclick =
      findRoute;

  }


});
