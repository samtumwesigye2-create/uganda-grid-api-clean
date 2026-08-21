window.addEventListener("load", function () {

const mapElement = document.getElementById("map");

if (!mapElement) {
    console.log("Map element missing");
    return;
}

const map = L.map("map").setView([1.3733,32.2903],7);


L.tileLayer(
"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
{
maxZoom:19,
attribution:"© OpenStreetMap"
}
).addTo(map);


const cities = [
["Kampala",0.3476,32.5825],
["Entebbe",0.0512,32.4637],
["Jinja",0.4479,33.2026],
["Mbarara",-0.6072,30.6545],
["Mbale",1.0821,34.175],
["Gulu",2.7746,32.299]
];


cities.forEach(city => {

L.marker([city[1],city[2]])
.addTo(map)
.bindPopup(city[0]);

});


let routeLine;


window.findRoute = function(){

let start =
document.getElementById("start").value.trim();

let destination =
document.getElementById("destination").value.trim();


let a = cities.find(
x => x[0].toLowerCase() === start.toLowerCase()
);

let b = cities.find(
x => x[0].toLowerCase() === destination.toLowerCase()
);


if(!a || !b){

alert("Use cities like Kampala and Jinja");

return;

}


if(routeLine){

map.removeLayer(routeLine);

}


routeLine = L.polyline(
[
[a[1],a[2]],
[b[1],b[2]]
],
{
color:"#d71920",
weight:6
}
).addTo(map);


map.fitBounds(routeLine.getBounds());

};


setTimeout(function(){

map.invalidateSize();

},500);


});
