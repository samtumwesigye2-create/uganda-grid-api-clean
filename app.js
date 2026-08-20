const API = "https://uganda-grid-api-clean-1.onrender.com";

const map = L.map("map").setView([1.3733, 32.2903], 7);

L.tileLayer(
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  }
).addTo(map);


// Route storage
let routeLine = null;
let selectedStart = null;
let selectedDestination = null;


// Search database
async function searchAddress(query) {

  const response = await fetch(
    API + "/search?q=" + encodeURIComponent(query)
  );

  const data = await response.json();

  return data.results || [];
}


// Find coordinates from database result
function getCoordinates(item) {

  if (item.latitude && item.longitude) {
    return [
      item.latitude,
      item.longitude
    ];
  }

  if (item.lat && item.lon) {
    return [
      item.lat,
      item.lon
    ];
  }

  return null;
}


// Route function
async function findRoute() {

  const start =
    document.getElementById("start").value;

  const destination =
    document.getElementById("destination").value;


  if (!start || !destination) {

    alert("Please enter both locations.");

    return;
  }


  const startResults =
    await searchAddress(start);


  const destinationResults =
    await searchAddress(destination);



  if (!startResults.length) {

    alert("Start location not found.");

    return;
  }


  if (!destinationResults.length) {

    alert("Destination not found.");

    return;
  }



  const startCoords =
    getCoordinates(startResults[0]);


  const destinationCoords =
    getCoordinates(destinationResults[0]);



  if (!startCoords || !destinationCoords) {

    alert("Coordinates unavailable.");

    return;
  }



  const url =
    "https://router.project-osrm.org/route/v1/driving/" +
    startCoords[1] + "," + startCoords[0] +
    ";" +
    destinationCoords[1] + "," + destinationCoords[0] +
    "?overview=full&geometries=geojson";



  const response =
    await fetch(url);


  const data =
    await response.json();



  if (!data.routes || !data.routes.length) {

    alert("No route found.");

    return;

  }



  const coordinates =
    data.routes[0]
    .geometry
    .coordinates
    .map(point => [
      point[1],
      point[0]
    ]);



  if (routeLine) {

    map.removeLayer(routeLine);

  }



  routeLine =
    L.polyline(
      coordinates,
      {
        color:"#d71920",
        weight:6
      }
    )
    .addTo(map);



  map.fitBounds(
    routeLine.getBounds(),
    {
      padding:[30,30]
    }
  );

}
