async function selectLocation(input, box, out, kind){

    const selected = input.dataset.selected;

    if(!selected){
        status.textContent =
        "Please select a real address from the suggestions.";
        
        status.className="status err";
        return;
    }


    const place = JSON.parse(selected);


    input.value = place.display_name;


    input.dataset.lat = place.lat;
    input.dataset.lon = place.lon;


    G(out).textContent =
    "✓ " + place.display_name;


    box.style.display="none";


    status.textContent =
    "✓ " + kind + " selected";

    status.className="status ok";

}




async function suggest(input,box,kind,out){

    const q=input.value.trim();


    if(q.length < 3){

        box.style.display="none";
        return;

    }



    const r = await fetch(

    "https://nominatim.openstreetmap.org/search?format=json&limit=5&countrycodes=ug&q="
    +
    encodeURIComponent(q)

    );


    const places = await r.json();



    box.innerHTML="";



    places.forEach(place=>{


        const div=document.createElement("div");


        div.textContent =
        place.display_name;



        div.onclick=function(){


            input.dataset.selected =
            JSON.stringify(place);


            input.value =
            place.display_name;


            input.dataset.lat =
            place.lat;


            input.dataset.lon =
            place.lon;


            box.style.display="none";


            G(out).textContent =
            "✓ "+place.display_name;



        };


        box.appendChild(div);


    });



    box.style.display =
    places.length ? "block":"none";

}
