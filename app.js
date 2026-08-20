const API = "https://sdpu1ajg41lf.ramnaymcloud.com";

const map = L.map("map").setView([1.3733, 32.2903], 7);

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap"
}).addTo(map);

let routeLine;
let startMarker;
let destinationMarker;

const cities = {
  Kampala: [0.3476, 32.5825],
  Entebbe: [0.0512, 32.4637],
  Jinja: [0.4479, 33.2026],
  Mbarara: [-0.6072, 30.6545],
  Mbale: [1.0821, 34.1750],
  Gulu: [2.7746, 32.2990],
  Arua: [3.0303, 30.9111],
  Soroti: [1.7146, 33.6111],
  Moroto: [2.5345, 34.6666],
  Hoima: [1.4331, 31.3524],
  Masaka: [-0.3476, 31.7330]
};

Object.entries(cities).forEach(([name, coords]) => {
  L.marker(coords)
    .addTo(map)
    .bindPopup(name);
});

function clearRoute() {
  if (routeLine) {
    map.removeLayer(routeLine);
  }

  if (startMarker) {
    map.removeLayer(startMarker);
  }

  if (destinationMarker) {
    map.removeLayer(destinationMarker);
  }

  routeLine = null;
  startMarker = null;
  destinationMarker = null;
}

function swapLocations() {
  let start = document.getElementById("start");
  let destination = document.getElementById("destination");

  let temp = start.value;

  start.value = destination.value;
  destination.value = temp;
}

function getCity(name) {
  let key = name.trim();

  for (let city in cities) {
    if (city.toLowerCase() === key.toLowerCase()) {
      return {
        coordinates: cities[city],
        name: city
      };
    }
  }

  return null;
}

async function searchAddress(text) {
  const response = await fetch(
    API + "/addresses/search?q=" + encodeURIComponent(text)
  );

  const data = await response.json();

  let results =
    data.results ||
    data.addresses ||
    [];

  if (!results.length) {
    return null;
  }

  let item = results[0];

  let lat =
    item.latitude ??
    item.lat;

  let lon =
    item.longitude ??
    item.lon ??
    item.lng;

  if (!lat || !lon) {
    return null;
  }

  return {
    coordinates: [
      Number(lat),
      Number(lon)
    ],
    name: text
  };
}

async function resolveLocation(value) {
  let city = getCity(value);

  if (city) {
    return city;
  }

  return await searchAddress(value);
}

async function findRoute() {
  let start =
    document.getElementById("start").value;

  let destination =
    document.getElementById("destination").value;

  if (!start || !destination) {
    alert("Enter start and destination");
    return;
  }

  let startLocation =
    await resolveLocation(start);

  let destinationLocation =
    await resolveLocation(destination);

  if (!startLocation || !destinationLocation) {
    alert("Location not found");
    return;
  }

  let a = startLocation.coordinates;
  let b = destinationLocation.coordinates;

  let url =
    "https://router.project-osrm.org/route/v1/driving/" +
    a[1] + "," + a[0] +
    ";" +
    b[1] + "," + b[0] +
    "?overview=full&geometries=geojson";

  let response =
    await fetch(url);

  let data =
    await response.json();

  if (!data.routes.length) {
    alert("No route found");
    return;
  }

  clearRoute();

  let points =
    data.routes[0]
    .geometry
    .coordinates
    .map(p => [
      p[1],
      p[0]
    ]);

  routeLine =
    L.polyline(points,{
      color:"#d71920",
      weight:6
    })
    .addTo(map);

  startMarker =
    L.marker(a)
    .addTo(map)
    .bindPopup("Start: " + startLocation.name);

  destinationMarker =
    L.marker(b)
    .addTo(map)
    .bindPopup("Destination: " + destinationLocation.name);

  map.fitBounds(
    routeLine.getBounds(),
    {
      padding:[30,30]
    }
  );
}
