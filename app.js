window.onload = function () {

const map = L.map("map").setView(
    [1.3733, 32.2903],
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
    ["Mbale",1.0821,34.1750],
    ["Gulu",2.7746,32.2990]

];



cities.forEach(function(city){

    L.marker([
        city[1],
        city[2]
    ])
    .addTo(map)
    .bindPopup(city[0]);

});



// ADDRESS SEARCH

function setupSearch(inputId, suggestionId){

const input = document.getElementById(inputId);
const box = document.getElementById(suggestionId);


if(!input || !box){
    return;
}



input.addEventListener("input", async function(){

let query = input.value;


if(query.length < 3){

    box.innerHTML="";
    return;

}



let response = await fetch(
"https://nominatim.openstreetmap.org/search?format=json&countrycodes=ug&q="
+ encodeURIComponent(query)
);



let results = await response.json();



box.innerHTML="";



results.slice(0,5).forEach(function(place){


let item=document.createElement("div");

item.innerText=place.display_name;

item.style.padding="10px";
item.style.background="white";
item.style.borderBottom="1px solid #ddd";
item.style.cursor="pointer";



item.onclick=function(){


    // KEEP SELECTED ADDRESS IN SEARCH BOX

    input.value = place.display_name;


    // STORE COORDINATES

    input.dataset.lat = place.lat;

    input.dataset.lon = place.lon;



    // CLOSE SUGGESTIONS

    box.innerHTML="";


};



box.appendChild(item);



});


});


}



setupSearch(
"start",
"startSug"
);


setupSearch(
"destination",
"endSug"
);





// ROUTE TEST

let routeLine = null;


window.findRoute=function(){


let start =
document.getElementById("start");


let destination =
document.getElementById("destination");



if(!start.dataset.lat || !destination.dataset.lat){

alert("Please select both addresses from the suggestions.");

return;

}



if(routeLine){

map.removeLayer(routeLine);

}



routeLine = L.polyline(

[
[
start.dataset.lat,
start.dataset.lon
],

[
destination.dataset.lat,
destination.dataset.lon
]
],

{
color:"red",
weight:6
}

)
.addTo(map);



map.fitBounds(
routeLine.getBounds()
);



};





setTimeout(function(){

map.invalidateSize();

},1000);



};
