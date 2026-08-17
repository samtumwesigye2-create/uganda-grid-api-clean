let map;
let addresses = [];
let marker;
let userMarker;
let currentLocation = null;

map = new maplibregl.Map({
  container: "map",
  style: "https://demotiles.maplibre.org/style.json",
  center: [32.46, 0.05],
  zoom: 12
});

map.addControl(new maplibregl.NavigationControl());

fetch("entebbe_database_import.csv")
  .then(r => r.text())
  .then(csv => {
    const rows = csv.trim().split(/\r?\n/);
    const headers = rows[0].split(",").map(h => h.trim());

    addresses = rows.slice(1).map(row => {
      const values = row.split(",");
      const obj = {};

      headers.forEach((h, i) => {
        obj[h] = values[i] || "";
      });

      return obj;
    });

    document.getElementById("message").textContent =
      "Address database loaded: " + addresses.length;
  })
  .catch(() => {
    document.getElementById("message").textContent =
      "Could not load address database.";
  });

function searchAddress() {
  const q = document
    .getElementById("searchInput")
    .value
    .toLowerCase()
    .trim();

  const result = addresses.find(a =>
    JSON.stringify(a).toLowerCase().includes(q)
  );

  const results = document.getElementById("results");

  if (!result) {
    results.innerHTML = "<p>Address not found</p>";
    return;
  }

  const lat = Number(result.latitude);
  const lng = Number(result.longitude);

  if (marker) {
    marker.remove();
  }

  marker = new maplibregl.Marker()
    .setLngLat([lng, lat])
    .addTo(map);

  map.flyTo({
    center: [lng, lat],
    zoom: 18
  });

  results.innerHTML = `
    <div class="result-card">
      <h2>${result.address || "Address found"}</h2>
      <p>Grid ID: ${result.grid_id || ""}</p>
      <p>Coordinates: ${lat}, ${lng}</p>
      <button onclick="findRouteTo(${lat},${lng})">
        🚗 Navigate Here
      </button>
    </div>
  `;
}
