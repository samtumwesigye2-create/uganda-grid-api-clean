export default {
  async fetch(request, env) {
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <title>Uganda National Grid</title>

  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  />

  <style>
    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f4f6f8;
      color: #17202a;
    }

    header {
      background: #111827;
      color: white;
      padding: 18px;
      text-align: center;
    }

    header h1 {
      margin: 0;
      font-size: 26px;
    }

    header p {
      margin: 6px 0 0;
      opacity: .8;
    }

    .search {
      background: white;
      padding: 18px;
      max-width: 1000px;
      margin: 18px auto;
      border-radius: 12px;
      box-shadow: 0 4px 15px rgba(0,0,0,.08);
    }

    label {
      display: block;
      font-weight: bold;
      margin-top: 10px;
    }

    input {
      width: 100%;
      padding: 13px;
      margin-top: 6px;
      border: 1px solid #ccc;
      border-radius: 7px;
      font-size: 16px;
    }

    button {
      margin-top: 16px;
      padding: 13px 22px;
      border: 0;
      border-radius: 7px;
      background: #d71920;
      color: white;
      font-size: 16px;
      cursor: pointer;
    }

    #map {
      height: 600px;
      width: 100%;
      max-width: 1100px;
      margin: 18px auto;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 15px rgba(0,0,0,.12);
    }

    #status {
      max-width: 1000px;
      margin: 10px auto;
      padding: 10px 18px;
      font-weight: bold;
    }
  </style>
</head>

<body>

<header>
  <h1>Uganda National Grid</h1>
  <p>National transportation and infrastructure network</p>
</header>

<section class="search">

  <label for="start">
    Start Location
  </label>

  <input
    id="start"
    placeholder="Enter starting location"
  />

  <label for="destination">
    Destination
  </label>

  <input
    id="destination"
    placeholder="Enter destination"
  />

  <button onclick="findRoute()">
    Find Route
  </button>

</section>

<div id="status">
  Loading Uganda map...
</div>

<div id="map"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<script>

  const map = L.map("map").setView([1.3733, 32.2903], 7);

  L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }
  ).addTo(map);

  const ugandaBounds = [
    [-1.5, 29.5],
    [4.3, 35.2]
  ];

  map.fitBounds(ugandaBounds);

  const cities = [
    {
      name: "Kampala",
      lat: 0.3476,
      lon: 32.5825
    },
    {
      name: "Jinja",
      lat: 0.4479,
      lon: 33.2026
    },
    {
      name: "Mbarara",
      lat: -0.6072,
      lon: 30.6545
    },
    {
      name: "Mbale",
      lat: 1.0821,
      lon: 34.1750
    },
    {
      name: "Gulu",
      lat: 2.7746,
      lon: 32.2990
    },
    {
      name: "Arua",
      lat: 3.0303,
      lon: 30.9111
    },
    {
      name: "Soroti",
      lat: 1.7146,
      lon: 33.6111
    },
    {
      name: "Moroto",
      lat: 2.5345,
      lon: 34.6666
    },
    {
      name: "Hoima",
      lat: 1.4331,
      lon: 31.3524
    },
    {
      name: "Masaka",
      lat: -0.3476,
      lon: 31.7330
    }
  ];

  cities.forEach(city => {

    L.marker([
      city.lat,
      city.lon
    ])
    .addTo(map)
    .bindPopup(
      "<strong>" + city.name + "</strong>"
    );

  });

  const gridLines = [

    [
      [0.3476, 32.5825],
      [0.4479, 33.2026],
      [1.0821, 34.1750]
    ],

    [
      [0.3476, 32.5825],
      [-0.3476, 31.7330],
      [-0.6072, 30.6545]
    ],

    [
      [0.3476, 32.5825],
      [1.4331, 31.3524],
      [2.7746, 32.2990],
      [3.0303, 30.9111]
    ],

    [
      [1.0821, 34.1750],
      [1.7146, 33.6111],
      [2.5345, 34.6666]
    ]

  ];

  gridLines.forEach(line => {

    L.polyline(
      line,
      {
        color: "#d71920",
        weight: 4,
        opacity: 0.8
      }
    ).addTo(map);

  });

  async function loadUgandaBoundary() {

    try {

      const response = await fetch(
        "https://raw.githubusercontent.com/georgique/world-geojson/master/countries/UGA.geo.json"
      );

      if (!response.ok) {
        throw new Error("Boundary unavailable");
      }

      const data = await response.json();

      L.geoJSON(
        data,
        {
          style: {
            color: "#111827",
            weight: 3,
            fillColor: "#facc15",
            fillOpacity: 0.15
          }
        }
      ).addTo(map);

      document.getElementById("status").textContent =
        "Uganda map loaded successfully.";

    } catch (error) {

      document.getElementById("status").textContent =
        "Uganda map loaded with national grid. Boundary data unavailable.";

    }

  }

  loadUgandaBoundary();

  function findRoute() {

    const start =
      document.getElementById("start").value.trim();

    const destination =
      document.getElementById("destination").value.trim();

    if (!start || !destination) {

      alert(
        "Please enter both a start location and destination."
      );

      return;

    }

    alert(
      "Route requested from " +
      start +
      " to " +
      destination
    );

  }

</script>

</body>
</html>`;

    return new Response(html, {
      headers: {
        "content-type": "text/html;charset=UTF-8"
      }
    });
  }
};
