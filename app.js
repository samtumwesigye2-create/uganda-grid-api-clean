const map = L.map("map").setView([1.3733, 32.2903], 7);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

let routeLine = null;
let selectedStart = null;
let selectedDestination = null;

const API = "";

const cities = {
  Kampala:[0.3476,32.5825], Entebbe:[0.0512,32.4637], Jinja:[0.4479,33.2026],
  Mbarara:[-0.6072,30.6545], Mbale:[1.0821,34.1750], Gulu:[2.7746,32.2990],
  Arua:[3.0303,30.9111], Soroti:[1.7146,33.6111], Moroto:[2.5345,34.6666],
  Hoima:[1.4331,31.3524], Masaka:[-0.3476,31.7330]
};

function getCity(name){
  for(const city in cities){
    if(city.toLowerCase()===name.trim().toLowerCase()){
      return {coordinates:cities[city],name:city};
    }
  }
  return null;
}

async function searchAddress(text, inputId){
  try{
    const r=await fetch(API+"/search?q="+encodeURIComponent(text));
    const data=await r.json();
    const results=data.results||[];

    const old=document.getElementById(inputId+"-suggestions");
    if(old) old.remove();

    if(!results.length) return;

    const box=document.createElement("div");
    box.id=inputId+"-suggestions";
    box.style.background="white";
    box.style.border="1px solid #ccc";
    box.style.position="absolute";
    box.style.zIndex="9999";

    results.slice(0,5).forEach(item=>{
      const div=document.createElement("div");
      div.style.padding="10px";
      div.style.cursor="pointer";
      div.textContent=item.grid_id || item.name || JSON.stringify(item);
      div.onclick=()=>{
        document.getElementById(inputId).value=div.textContent;
        const lat=item.latitude ?? item.lat;
        const lon=item.longitude ?? item.lon ?? item.lng;
        const location={coordinates:[Number(lat),Number(lon)],name:div.textContent};
        if(inputId==="start") selectedStart=location;
        if(inputId==="destination") selectedDestination=location;
        box.remove();
        map.setView(location.coordinates,14);
      };
      box.appendChild(div);
    });

    document.body.appendChild(box);
  }catch(e){console.error(e);}
}

async function resolve(value, selected){
  return selected || getCity(value);
}

async function findRoute(){
  const start=document.getElementById("start").value;
  const destination=document.getElementById("destination").value;

  const a=await resolve(start,selectedStart);
  const b=await resolve(destination,selectedDestination);

  if(!a||!b){alert("Location not found");return;}

  const url="https://router.project-osrm.org/route/v1/driving/"+
    a.coordinates[1]+","+a.coordinates[0]+";"+
    b.coordinates[1]+","+b.coordinates[0]+"?overview=full&geometries=geojson";

  const response=await fetch(url);
  const data=await response.json();

  if(!data.routes.length){alert("No route found");return;}

  if(routeLine) map.removeLayer(routeLine);

  routeLine=L.polyline(
    data.routes[0].geometry.coordinates.map(p=>[p[1],p[0]]),
    {color:"#d71920",weight:6}
  ).addTo(map);

  map.fitBounds(routeLine.getBounds(),{padding:[30,30]});
}

document.getElementById("start")?.addEventListener("input",e=>{
  selectedStart=null;
  if(e.target.value.length>2) searchAddress(e.target.value,"start");
});

document.getElementById("destination")?.addEventListener("input",e=>{
  selectedDestination=null;
  if(e.target.value.length>2) searchAddress(e.target.value,"destination");
});
