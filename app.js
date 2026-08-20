const map = L.map("map").setView([1.3733, 32.2903], 7);

L.tileLayer(
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  }
).addTo(map);


// Uganda cities
const cities = [
  ["Kampala", 0.3476, 32.5825],
  ["Entebbe", 0.0512, 32.4637],
  ["Jinja", 0.4479, 33.2026],
  ["Mbarara", -0.6072, 30.6545],
  ["Mbale", 1.0821, 34.1750],
  ["Gulu", 2.7746, 32.2990],
  ["Arua", 3.0303, 30.9111],
  ["Soroti", 1.7146, 33.6111],
  ["Moroto", 2.5345, 34.6666],
  ["Hoima", 1.4331, 31.3524],
  ["Masaka", -0.3476, 31.7330]
];


// Add city markers
cities.forEach(city => {

  L.marker([city[1], city[2]])
    .addTo(map)
    .bindPopup("<strong>" + city[0] + "</strong>");

});


// Current route
let routeLine = null;
let startMarker = null;
let destinationMarker = null;


// Find city coordinates
function findCity(name) {

  name = name.trim().toLowerCase();

  for (const city of cities) {

    if (city[0].toLowerCase() === name) {

      return [
        city[1],
        city[2]
      ];

    }
  }

  return null;
}


// Clear route
function clearRoute() {

  if (routeLine) {
    map.removeLayer(routeLine);
    routeLine = null;
  }

  if (startMarker) {
    map.removeLayer(startMarker);
    startMarker = null;
  }

  if (destinationMarker) {
    map.removeLayer(destinationMarker);
    destinationMarker = null;
  }

}


// Swap start and destination
function swapLocations() {

  const start =
    document.getElementById("start");

  const destination =
    document.getElementById("destination");


  const temp = start.value;

  start.value = destination.value;

  destination.value = temp;

}



// Route function
async function findRoute() {

  const start =
    document.getElementById("start").value;

  const destination =
    document.getElementById("destination").value;


  if (!start || !destination) {

    alert(
      "Please enter both a start location and destination."
    );

    return;
  }


  const startCoords = findCity(start);

  const destinationCoords = findCity(destination);


  if (!startCoords) {

    alert(
      "Start location not found. Try a major Ugandan city."
    );

    return;
  }


  if (!destinationCoords) {

    alert(
      "Destination not found. Try a major Ugandan city."
    );

    return;
  }



  const url =
    "https://router.project-osrm.org/route/v1/driving/" +
    startCoords[1] + "," + startCoords[0] +
    ";" +
    destinationCoords[1] + "," + destinationCoords[0] +
    "?overview=full&geometries=geojson";



  try {

    const response = await fetch(url);

    const data = await response.json();


    if (!data.routes || data.routes.length === 0) {

      alert("No route found.");

      return;
    }



    clearRoute();


    const route =
      data.routes[0];


    const coordinates =
      route.geometry.coordinates.map(
        point => [point[1], point[0]]
      );



    routeLine =
      L.polyline(
        coordinates,
        {
          color: "#d71920",
          weight: 6
        }
      ).addTo(map);



    startMarker =
      L.marker(startCoords)
      .addTo(map)
      .bindPopup("Start: " + start);



    destinationMarker =
      L.marker(destinationCoords)
      .addTo(map)
      .bindPopup("Destination: " + destination);



    map.fitBounds(
      routeLine.getBounds(),
      {
        padding: [30, 30]
      }
    );


  } catch (error) {

    console.error(error);

    alert(
      "Unable to calculate the route right now."
    );

  }

}
