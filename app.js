window.onload=function(){

const map=L.map("map").setView(
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



const cities=[

["Kampala",0.3476,32.5825],
["Jinja",0.4479,33.2026],
["Entebbe",0.0512,32.4637],
["Mbarara",-0.6072,30.6545],
["Mbale",1.0821,34.1750]

];



cities.forEach(function(c){

L.marker(
[c[1],c[2]]
)
.addTo(map)
.bindPopup(c[0]);

});



// ADDRESS SEARCH

function setupSearch(inputId,suggestionId){

const input=document.getElementById(inputId);
const box=document.getElementById(suggestionId);


if(!input || !box){
return;
}


input.addEventListener("input",async function(){

let q=input.value;


if(q.length < 3){

box.innerHTML="";
return;

}


let response=await fetch(
"https://nominatim.openstreetmap.org/search?format=json&countrycodes=ug&q="+q
);


let results=await response.json();


box.innerHTML="";


results.slice(0,5).forEach(function(place){


let item=document.createElement("div");

item.style.padding="10px";
item.style.cursor="pointer";
item.style.background="white";
item.style.borderBottom="1px solid #ddd";


item.innerText=place.display_name;



item.onclick=function(){

// KEEP ADDRESS IN SEARCH BOX

input.value=place.display_name;


// SAVE COORDINATES

input.dataset.lat=place.lat;
input.dataset.lon=place.lon;


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





window.findRoute=function(){

let start=document.getElementById("start").value;

let destination=document.getElementById("destination").value;


alert(
"Route from:\n"+
start+
"\nTo:\n"+
destination
);


};





setTimeout(function(){

map.invalidateSize();

},1000);


};
