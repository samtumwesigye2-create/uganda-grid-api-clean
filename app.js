window.addEventListener("load", function () {

    const map = L.map("map").setView([1.3733, 32.2903], 7);

    L.tileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,
            attribution: "© OpenStreetMap"
        }
    ).addTo(map);


    const cities = [
        ["Kampala",0.3476,32.5825],
        ["Jinja",0.4479,33.2026],
        ["Entebbe",0.0512,32.4637],
        ["Mbarara",-0.6072,30.6545],
        ["Mbale",1.0821,34.175]
    ];


    cities.forEach(function(city){

        L.marker([
            city[1],
            city[2]
        ])
        .addTo(map)
        .bindPopup(city[0]);

    });


    setTimeout(function(){
        map.invalidateSize();
    },500);

});
