window.onload = function(){

const map = L.map("map").setView(
    [1.3733,32.2903],
    7
);


L.tileLayer(
"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
{
maxZoom:19,
attribution:"© OpenStreetMap"
}
).addTo(map);



const cities = [

["Kampala",0.3476,32.5825],
["Jinja",0.4479,33.2026],
["Entebbe",0.0512,32.4637],
["Mbarara",-0.6072,30.6545],
["Mbale",1.0821,34.1750]

];



cities.forEach(function(city){

L.marker([
city[1],
city[2]
])
.addTo(map)
.bindPopup(city[0]);

});



let routeLine = null;



function drawRoute(){


let start =
document.getElementById("start");


let destination =
document.getElementById("destination");



if(!start || !destination){

alert("Location fields missing");

return;

}



if(!start.value || !destination.value){

alert("Enter both locations");

return;

}



let startCity =
cities.find(
c => c[0].toLowerCase() === start.value.toLowerCase()
);



let endCity =
cities.find(
c => c[0].toLowerCase() === destination.value.toLowerCase()
);



if(!startCity || !endCity){

alert(
"Use Uganda cities like Kampala and Jinja"
);

return;

}




if(routeLine){

map.removeLayer(routeLine);

}



routeLine = L.polyline(

[
[startCity[1],startCity[2]],
[endCity[1],endCity[2]]
],

{
color:"#d71920",
weight:6
}

)

.addTo(map);



map.fitBounds(
routeLine.getBounds()
);



alert(
"Navigation started"
);



}




// OLD BUTTON SUPPORT

window.findRoute = function(){

drawRoute();

};



// NEW BUTTON SUPPORT

window.startNavigation = function(){

drawRoute();

};





setTimeout(function(){

map.invalidateSize();

},1000);



};
