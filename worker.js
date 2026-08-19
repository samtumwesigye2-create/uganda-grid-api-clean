export default {
  async fetch(request, env) {
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Uganda National Grid</title>
  <style>
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f4f6f8;
      color: #17202a;
    }

    header {
      background: #111827;
      color: white;
      padding: 20px;
      text-align: center;
    }

    header h1 {
      margin: 0;
      font-size: 28px;
    }

    header p {
      margin: 6px 0 0;
      opacity: .8;
    }

    .search {
      background: white;
      padding: 20px;
      max-width: 900px;
      margin: 20px auto;
      border-radius: 12px;
      box-shadow: 0 4px 15px rgba(0,0,0,.08);
    }

    label {
      display: block;
      font-weight: bold;
      margin-top: 12px;
    }

    input {
      width: 100%;
      box-sizing: border-box;
      padding: 13px;
      margin-top: 6px;
      border: 1px solid #ccc;
      border-radius: 7px;
      font-size: 16px;
    }

    button {
      margin-top: 18px;
      padding: 13px 22px;
      border: 0;
      border-radius: 7px;
      background: #d71920;
      color: white;
      font-size: 16px;
      cursor: pointer;
    }

    #map {
      height: 500px;
      max-width: 900px;
      margin: 20px auto;
      background: #dbeafe;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #374151;
      font-size: 20px;
    }
  </style>
</head>

<body>
  <header>
    <h1>Uganda National Grid</h1>
    <p>National transportation and infrastructure network</p>
  </header>

  <section class="search">
    <label for="start">Start Location</label>
    <input id="start" placeholder="Enter starting location">

    <label for="destination">Destination</label>
    <input id="destination" placeholder="Enter destination">

    <button onclick="findRoute()">Find Route</button>
  </section>

  <div id="map">
    Uganda National Grid Map
  </div>

  <script>
    function findRoute() {
      const start = document.getElementById("start").value;
      const destination = document.getElementById("destination").value;

      if (!start || !destination) {
        alert("Please enter both a start location and destination.");
        return;
      }

      alert("Route requested from " + start + " to " + destination);
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
