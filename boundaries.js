(function () {
  if (!window.L) return;

  const originalMap = L.map;
  let initialized = false;

  function installRouteBranding() {
    const logo = document.querySelector('.mapHeaderLogo');
    if (!logo) return;
    const originalSrc = logo.getAttribute('src') || '';
    // Fix: previously fetched a giant base64 .txt file at runtime, which kept
    // arriving corrupted/truncated and produced a broken image during nav.
    // Point straight at the PNG file instead - no fetch, no text parsing,
    // browser caches it normally like any other image.
    const routeSrc = '/assets/ugamap-nav-icon.png';
    if (!document.getElementById('ugamap-route-brand-style')) {
      const style = document.createElement('style');
      style.id = 'ugamap-route-brand-style';
      style.textContent = 'body.navigating header .mapHeaderText{display:none!important}body.navigating header .titleWrap{justify-content:center!important}body.navigating header .mapHeaderLogo{width:42px!important;height:42px!important;object-fit:contain!important;background:transparent!important;border-radius:0!important}';
      document.head.appendChild(style);
    }
    function syncRouteBranding() {
      const navigating = document.body.classList.contains('navigating');
      const wanted = navigating ? routeSrc : originalSrc;
      if (logo.getAttribute('src') !== wanted) logo.setAttribute('src', wanted);
      logo.alt = navigating ? 'UGAMAP' : 'Uganda National Grid';
    }
    new MutationObserver(syncRouteBranding).observe(document.body,{attributes:true,attributeFilter:['class']});
    syncRouteBranding();
  }
  installRouteBranding();

  async function getJson(path) {
    const r = await fetch(path,{headers:{Accept:'application/json'},cache:'no-store'});
    if (!r.ok) throw new Error(path+' returned HTTP '+r.status);
    return r.json();
  }

  async function safeGeoJson(path) {
    try {
      const data = await getJson(path);
      if (data && data.type === 'FeatureCollection' && Array.isArray(data.features)) return data;
      throw new Error(path+' did not return a GeoJSON FeatureCollection');
    } catch (e) {
      console.error('UGAMAP geography source unavailable:', path, e);
      return {type:'FeatureCollection',features:[]};
    }
  }

  async function initializeBoundaries(map) {
    if (initialized || !map) return;
    initialized = true;
    try {
      const [states,zips,specialZips] = await Promise.all([
        safeGeoJson('/geography/states'),
        safeGeoJson('/geography/zips'),
        safeGeoJson('/geography/special-zips')
      ]);

      const stateLayer = L.geoJSON(states, {
        style:{color:'#f59e0b',weight:3,fillColor:'#f59e0b',fillOpacity:.015},
        onEachFeature:function(f,layer){
          const p=f.properties||{};
          const name=p.state_name||p.state_code||'State';
          const postalPrefix=p.postal_prefix||'';
          const gridPrefix=p.grid_prefix||'';
          layer.bindPopup('<b>'+name+'</b><br>State: '+(p.state_code||'')+'<br>Grid prefix: '+gridPrefix+'<br>Postal prefix: '+postalPrefix);
          layer._ugamapStateLabel=postalPrefix?(name+' · ZIP '+postalPrefix):name;
        }
      });

      const palette=['#38bdf8','#22c55e','#facc15','#c084fc','#fb7185','#2dd4bf','#fb923c','#60a5fa','#a3e635','#f472b6'];
      const zipLayer = L.geoJSON(zips, {
        style:function(f){
          const zip=String((f.properties||{}).zip_code||'');
          const n=Number(zip.slice(-2))||1;
          const color=palette[(n-1)%palette.length];
          return{color:color,weight:1.5,dashArray:'5 4',fillColor:color,fillOpacity:.12};
        },
        onEachFeature:function(f,layer){
          const p=f.properties||{};
          const zip=p.zip_code||'';
          layer.bindPopup('<b>Geographic ZIP '+zip+'</b><br>'+(p.state_name||'')+'<br>Region: '+(p.postal_region||'')+'<br><small>Special national facilities inside this area may have their own 00xxx ZIP.</small>');
          layer._ugamapZip=zip;
        }
      });

      const specialLayer = L.geoJSON(specialZips, {
        pointToLayer:function(f,latlng){return L.circleMarker(latlng,{radius:10,color:'#ffffff',weight:2,fillColor:'#7c3aed',fillOpacity:1});},
        onEachFeature:function(f,layer){
          const p=f.properties||{};
          const zip=p.zip_code||'';
          const name=p.name||'National Special Facility';
          const category=String(p.category||'').replace(/_/g,' ');
          layer.bindPopup('<b>Special ZIP '+zip+'</b><br>'+name+(category?'<br>Category: '+category:'')+(p.address?'<br>'+p.address:''));
          layer._ugamapSpecialZip=zip;
          layer._ugamapSpecialName=name;
        }
      });

      if(!document.getElementById('ugamap-boundary-style')){
        const style=document.createElement('style');
        style.id='ugamap-boundary-style';
        style.textContent='.ugamap-zip-label{background:rgba(8,15,30,.86);color:#fff;border:1px solid rgba(255,255,255,.35);border-radius:5px;box-shadow:none;font-weight:700;font-size:10px;padding:2px 4px}.ugamap-zip-label:before{display:none}.ugamap-state-prefix{background:rgba(8,15,30,.92);color:#ffd166;border:1px solid rgba(245,158,11,.9);border-radius:7px;box-shadow:0 2px 8px rgba(0,0,0,.35);font-weight:800;font-size:11px;padding:3px 6px;white-space:nowrap}.ugamap-state-prefix:before{display:none}.ugamap-special-zip{background:#5b21b6;color:#fff;border:2px solid #fff;border-radius:7px;box-shadow:0 2px 8px rgba(0,0,0,.4);font-weight:900;font-size:11px;padding:3px 6px;white-space:nowrap}.ugamap-special-zip:before{display:none}';
        document.head.appendChild(style);
      }

      function ensureLabelsVisible(){
        zipLayer.eachLayer(function(layer){
          const zip=layer._ugamapZip;
          if(!zip)return;
          if(!layer.getTooltip())layer.bindTooltip(String(zip),{permanent:true,direction:'center',className:'ugamap-zip-label',opacity:.92});
          layer.openTooltip();
        });
        stateLayer.eachLayer(function(layer){
          const label=layer._ugamapStateLabel;
          if(!label)return;
          if(!layer.getTooltip())layer.bindTooltip(label,{permanent:true,direction:'center',className:'ugamap-state-prefix',opacity:.96});
          layer.openTooltip();
        });
        specialLayer.eachLayer(function(layer){
          const zip=layer._ugamapSpecialZip;
          const name=layer._ugamapSpecialName;
          if(!zip)return;
          if(!layer.getTooltip())layer.bindTooltip(zip+(name?' · '+name:''),{permanent:true,direction:'top',className:'ugamap-special-zip',opacity:.98,offset:[0,-8]});
          layer.openTooltip();
        });
      }

      L.control.layers(null,{
        'State Boundaries':stateLayer,
        'ZIP Zones':zipLayer,
        'National Special ZIPs':specialLayer
      },{collapsed:true,position:'topright'}).addTo(map);

      stateLayer.addTo(map);
      zipLayer.addTo(map);
      specialLayer.addTo(map);
      ensureLabelsVisible();
      map.on('zoomend moveend layeradd',ensureLabelsVisible);
      setTimeout(ensureLabelsVisible,250);
      setTimeout(ensureLabelsVisible,1000);

      window.UGAMAP=window.UGAMAP||{};
      window.UGAMAP.boundaries={states:stateLayer,zips:zipLayer,specialZips:specialLayer,updateLabels:ensureLabelsVisible};
    } catch(e){
      initialized=false;
      console.error('Boundary layers unavailable:',e);
    }
  }

  L.map=function(){
    const map=originalMap.apply(this,arguments);
    window.__UGAMAP_LEAFLET_MAP__=map;
    setTimeout(function(){initializeBoundaries(map);},0);
    return map;
  };
  Object.keys(originalMap).forEach(function(k){try{L.map[k]=originalMap[k];}catch(_){}});
})();
