(function () {
  if (!window.L) return;

  const originalMap = L.map;
  let initialized = false;

  const API_BASES = (() => {
    const out = [];
    if (location.protocol && location.protocol.indexOf('http') === 0) out.push(location.origin);
    out.push('https://uganda-grid-api-clean-production.up.railway.app');
    return Array.from(new Set(out));
  })();

  async function getJson(path) {
    let lastError = null;
    for (const base of API_BASES) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        const r = await fetch(base + path, {headers:{Accept:'application/json'},cache:'no-store',signal:controller.signal});
        clearTimeout(timer);
        if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
        return await r.json();
      } catch (e) { lastError = e; }
    }
    throw lastError || new Error(path + ' unavailable');
  }

  async function safeGeoJson(path) {
    try {
      const data = await getJson(path);
      return data && data.type === 'FeatureCollection' && Array.isArray(data.features)
        ? data : {type:'FeatureCollection',features:[]};
    } catch (e) {
      console.error('UGAMAP geography source unavailable:', path, e);
      return {type:'FeatureCollection',features:[]};
    }
  }

  function explicitFiveDigitId(p) {
    const candidates = [p.zipper_id, p.zip_code, p.zip, p.postal_code];
    for (const v of candidates) {
      const s = String(v == null ? '' : v).trim();
      if (/^\d{5}$/.test(s)) return s;
    }
    return null;
  }

  async function initializeBoundaries(map) {
    if (initialized || !map) return;
    initialized = true;

    try {
      const [states,zips] = await Promise.all([
        safeGeoJson('/geography/states'),
        safeGeoJson('/geography/zipper')
      ]);

      const stateLayer = L.geoJSON(states, {
        style:{color:'#f59e0b',weight:2.2,fillColor:'#f59e0b',fillOpacity:.01},
        onEachFeature:function(f,layer){
          const p=f.properties||{};
          const name=p.state_name||p.state_code||'State';
          layer._ugamapStateLabel=name;
          layer.bindPopup('<b>'+name+'</b>');
        }
      });

      let generatedIndex = 0;
      const palette=['#38bdf8','#22c55e','#facc15','#c084fc','#fb7185','#2dd4bf','#fb923c','#60a5fa','#a3e635','#f472b6'];
      const zipLayer = L.geoJSON(zips, {
        style:function(f){
          const p=f.properties||{};
          const explicit=explicitFiveDigitId(p);
          const n=explicit ? Number(explicit.slice(-2)) : generatedIndex + 1;
          const color=palette[(n-1)%palette.length];
          return {color:color,weight:.9,fillColor:color,fillOpacity:.08};
        },
        onEachFeature:function(f,layer){
          const p=f.properties||{};
          const explicit=explicitFiveDigitId(p);
          const numeric=explicit || String(10000 + generatedIndex).padStart(5,'0');
          generatedIndex += 1;

          const pop=Number(p.population||0);
          const district=p.district||'';
          const density=p.density_class||'';

          layer._ugamapZip=numeric;
          layer.bindPopup(
            '<b>ZIPPER '+numeric+'</b>'+
            (pop?'<br>Estimated population: '+pop.toLocaleString():'')+
            (district?'<br>'+district:'')+
            (density?'<br><small>'+density+'</small>':'')
          );
        }
      });

      if(!document.getElementById('ugamap-boundary-style')){
        const style=document.createElement('style');
        style.id='ugamap-boundary-style';
        style.textContent='.ugamap-zip-label{background:rgba(8,15,30,.90);color:#fff;border:1px solid rgba(56,189,248,.85);border-radius:5px;box-shadow:none;font-weight:800;font-size:10px;padding:2px 5px}.ugamap-zip-label:before{display:none}.ugamap-state-prefix{background:rgba(8,15,30,.92);color:#ffd166;border:1px solid rgba(245,158,11,.9);border-radius:7px;box-shadow:0 2px 8px rgba(0,0,0,.35);font-weight:800;font-size:11px;padding:3px 6px;white-space:nowrap}.ugamap-state-prefix:before{display:none}';
        document.head.appendChild(style);
      }

      const ZIPPER_MIN_ZOOM=11;
      const ZIPPER_LABEL_ZOOM=13;
      let zipperVisible=false;

      function sync(){
        const zoom=map.getZoom();
        const shouldShow=zoom>=ZIPPER_MIN_ZOOM;
        if(shouldShow&&!zipperVisible){zipLayer.addTo(map);zipperVisible=true;}
        if(!shouldShow&&zipperVisible){map.removeLayer(zipLayer);zipperVisible=false;}

        zipLayer.eachLayer(function(layer){
          const zip=layer._ugamapZip;
          if(!zip)return;
          if(zoom>=ZIPPER_LABEL_ZOOM){
            if(!layer.getTooltip()) layer.bindTooltip(zip,{permanent:true,direction:'center',className:'ugamap-zip-label',opacity:.95});
            layer.openTooltip();
          }else if(layer.getTooltip()) layer.unbindTooltip();
        });

        stateLayer.eachLayer(function(layer){
          const label=layer._ugamapStateLabel;
          if(!label)return;
          if(zoom<=9){
            if(!layer.getTooltip()) layer.bindTooltip(label,{permanent:true,direction:'center',className:'ugamap-state-prefix',opacity:.96});
            layer.openTooltip();
          }else if(layer.getTooltip()) layer.unbindTooltip();
        });
      }

      stateLayer.addTo(map);
      L.control.layers(null,{'State Boundaries':stateLayer,'5-digit ZIPPER':zipLayer},{collapsed:true,position:'topright'}).addTo(map);
      sync();
      map.on('zoomend moveend',sync);
      setTimeout(sync,400);

      window.UGAMAP=window.UGAMAP||{};
      window.UGAMAP.boundaries={states:stateLayer,zips:zipLayer,updateLabels:sync,minZoom:ZIPPER_MIN_ZOOM,labelZoom:ZIPPER_LABEL_ZOOM};
    } catch(e) {
      initialized=false;
      console.error('ZIPPER layer unavailable:',e);
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