const API = "https://sdpu1ajg41lf.ramnaymcloud.com";

const map = L.map("map").setView([1.3733, 32.2903], 7);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

let routeLine = null;
let startMarker = null;
let destinationMarker = null;

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

cities.forEach(city => {
  L.marker([city[1], city[2]])
    .addTo(map)
    .bindPopup("<strong>" + city[0] + "</strong>");
});

function findCity(name) {
  name = name.trim().toLowerCase();

  for (const city of cities) {
    if (city[0].toLowerCase() === name) {
      return [city[1], city[2]];
    }
  }

  return null;
}

async function searchDatabase(query) {
  const response = await fetch(
    API + "/addresses/search?q=" + encodeURIComponent(query)
  );

  if (!response.ok) {
    throw new Error("Search failed");
  }

  const data = await response.json();
  return data.results || data.addresses || [];
}

function getCoordinates(item) {
  const lat = item.latitude ?? item.lat;
  const lon = item.longitude ?? item.lon ?? item.lng;

  if (lat !== undefined && lon !== undefined) {
    return [Number(lat), Number(lon)];
  }

  return null;
}

async function resolveLocation(value) {
  const city = findCity(value);

  if (city) {
    return {
      coordinates: city,
      name: value
    };
  }

  const results = await searchDatabase(value);

  if (!results.length) {
    return null;
  }

  const coordinates = getCoordinates(results[0]);

  if (!coordinates) {
    return null;
  }

  return {
    coordinates,
    name: value,
    data: results[0]
  };
}

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

function swapLocations() {
  const startInput = document.getElementById("start");
  const destinationInput = document.getElementById("destination");

  const oldStart = startInput.value;

  startInput.value = destinationInput.value;
  destinationInput.value = oldStart;

  if (startInput.value && destinationInput.value) {
    findRoute();
  }
}

async function findRoute() {
  const start = document.getElementById("start").value.trim();
  const destination = document.getElementById("destination").value.trim();

  if (!start || !destination) {
    alert("Please enter both locations.");
    return;
  }

  try {
    const startLocation = await resolveLocation(start);
    const destinationLocation = await resolveLocation(destination);

    if (!startLocation) {
      alert("Start location not found.");
      return;
    }

    if (!destinationLocation) {
      alert("Destination not found.");
      return;
    }

    const startCoords = startLocation.coordinates;
    const destinationCoords = destinationLocation.coordinates;

    const url =
      "https://router.project-osrm.org/route/v1/driving/" +
      startCoords[1] + "," + startCoords[0] +
      ";" +
      destinationCoords[1] + "," + destinationCoords[0] +
      "?overview=full&geometries=geojson";

    const response = await fetch(url);
    const data = await response.json();

    if (!data.routes || !data.routes.length) {
      alert("No route found.");
      return;
    }

    clearRoute();

    const coordinates = data.routes[0].geometry.coordinates.map(
      point => [point[1], point[0]]
    );

    routeLine = L.polyline(coordinates, {
      color: "#d71920",
      weight: 6
    }).addTo(map);

    startMarker = L.marker(startCoords)
      .addTo(map)
      .bindPopup("Start: " + startLocation.name);

    destinationMarker = L.marker(destinationCoords)
      .addTo(map)
      .bindPopup("Destination: " + destinationLocation.name);

    map.fitBounds(routeLine.getBounds(), {
      padding: [30, 30]
    });
  } catch (error) {
    console.error(error);
    alert("Unable to search or calculate the route right now.");
  }
}

document.getElementById("destination").addEventListener("change", () => {
  const start = document.getElementById("start").value.trim();
  const destination = document.getElementById("destination").value.trim();

  if (start && destination) {
    findRoute();
  }
});
