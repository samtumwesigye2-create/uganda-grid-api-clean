// Uganda National Address Finder - Navigation Engine

let map;
let routeLayer = null;

const ROUTER = "https://router.project-osrm.org";

function initMap() {
  map = new maplibregl.Map({
    container: "map",
    style: "https://demotiles.maplibre.org/style.json",
    center: [32.4216, 0.1491],
    zoom: 13
  });

  map.addControl(new maplibregl.NavigationControl());
}

async function geocodeAddress(address) {
  const url =
    "https://nominatim.openstreetmap.org/search?format=json&q=" +
    encodeURIComponent(address + ", Uganda");

  const response = await fetch(url);
  const data = await response.json();

  if (!data.length) {
    throw new Error("Address not found");
  }

  return {
    longitude: Number(data[0].lon),
    latitude: Number(data[0].lat)
  };
}


async function findRoute() {

  const from =
    document.getElementById("fromInput").value;

  const to =
    document.getElementById("toInput").value;


  if (!from || !to) {
    alert("Enter both addresses");
    return;
  }


  try {

    async function geocodeAddress(address) {

  const api =
    "https://uganda-grid-api-clean-production.up.railway.app/address/" +
    encodeURIComponent(address);

  const response = await fetch(api);

  if (response.ok) {
    const data = await response.json();

    return {
      longitude: Number(data.longitude),
      latitude: Number(data.latitude),
      address: data.address
    };
  }


  // fallback to OpenStreetMap
  const url =
    "https://nominatim.openstreetmap.org/search?format=json&q=" +
    encodeURIComponent(address + ", Uganda");

  const osmResponse = await fetch(url);
  const osmData = await osmResponse.json();

  if (!osmData.length) {
    throw new Error("Address not found");
  }

  return {
    longitude: Number(osmData[0].lon),
    latitude: Number(osmData[0].lat),
    address: osmData[0].display_name
  };
}
    


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
      "?overview=full&geometries=geojson&steps=true";


    const response = await fetch(url);
    const data = await response.json();


    if (!data.routes.length) {
      alert("No driving route found");
      return;
    }


    const route = data.routes[0];


    if (routeLayer) {
      map.removeLayer("route");
      map.removeSource("route");
    }


    map.addSource("route", {
      type: "geojson",
      data: {
        type: "Feature",
        geometry: route.geometry
      }
    });


    map.addLayer({
      id: "route",
      type: "line",
      source: "route",
      paint: {
        "line-width": 5
      }
    });


    map.fitBounds(
      [
        [start.longitude, start.latitude],
        [end.longitude, end.latitude]
      ],
      {padding:50}
    );


    document.getElementById("routeInfo").innerHTML =
      `
      <h3>Driving Route</h3>
      <p>
      Distance:
      ${(route.distance / 1000).toFixed(2)}
      km
      </p>

      <p>
      Time:
      ${(route.duration / 60).toFixed(0)}
      minutes
      </p>
      `;


  } catch(error){

    console.error(error);

    alert(
      "Navigation error. Check addresses."
    );

  }

}


document.addEventListener(
"DOMContentLoaded",
function(){

  initMap();

  const button =
    document.getElementById("routeButton");

  if(button){
    button.addEventListener(
      "click",
      findRoute
    );
  }

});
