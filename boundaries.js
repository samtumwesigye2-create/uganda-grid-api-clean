(function () {
  if (!window.L) return;

  const originalMap = L.map;
  let initialized = false;
  const GEO_CACHE = 'ugamap-geography-v1';

  const API_BASES = (() => {
    const out = [];
    if (location.protocol && location.protocol.indexOf('http') === 0) out.push(location.origin);
    out.push('https://uganda-grid-api-clean-production.up.railway.app');
    return Array.from(new Set(out));
  })();

  async function cacheGet(url) {
    if (!('caches' in window)) return null;
    try {
      const cache = await caches.open(GEO_CACHE);
      const hit = await cache.match(url);
      if (!hit) return null;
      return await hit.json();
    } catch (_) { return null; }
  }

  async function cachePut(url, response) {
    if (!('caches' in window)) return;
    try {
      const cache = await caches.open(GEO_CACHE);
      await cache.put(url, response.clone());
    } catch (_) {}
  }

  async function networkJson(url, path) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 9000);
    try {
      const r = await fetch(url, {headers:{Accept:'application/json'},cache:'no-cache',signal:controller.signal});
      if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
      cachePut(url, r);
      return await r.json();
    } finally {
      clearTimeout(timer);
    }
  }

  async function getJson(path) {
    let lastError = null;
    for (const base of API_BASES) {
      const url = base + path;
      const cached = await cacheGet(url);
      if (cached) {
        networkJson(url, path).catch(function(){});
        return cached;
      }
      try {
        return await networkJson(url, path);
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

  function fiveDigitId(p, index) {
    const candidates=[p.primary_zip,p.primaryZip,p.zipper_number,p.zipperNumber,p.zipper_id,p.zip_code,p.zip,p.postal_code];
    for(const v of candidates){
      const s=String(v==null?'':v).trim();
      if(/^\d{5}$/.test(s)) return s;
    }
    return String(10000 + index).slice(-5).padStart(5,'0');
  }

  function featureBounds(feature){
    try {
      const coords = feature && feature.geometry && feature.geometry.coordinates;
      if (!coords) return null;
      let minLat=Infinity,minLon=Infinity,maxLat=-Infinity,maxLon=-Infinity;
      (function walk(v){
        if (!Array.isArray(v)) return;
        if (v.length>=2 && typeof v[0]==='number' && typeof v[1]==='number') {
          const lon=v[0], lat=v[1];
          if (Number.isFinite(lat) && Number.isFinite(lon)) {
            if(lat<minLat)minLat=lat;if(lat>maxLat)maxLat=lat;
            if(lon<minLon)minLon=lon;if(lon>maxLon)maxLon=lon;
          }
          return;
        }
        for(const x of v) walk(x);
      })(coords);
      if(!Number.isFinite(minLat)) return null;
      return L.latLngBounds([minLat,minLon],[maxLat,maxLon]);
    } catch(_) { return null; }
  }

  async function initializeBoundaries(map) {
    if (initialized || !map) return;
    initialized = true;

    try {
      const states = await safeGeoJson('/geography/states');
      const stateCanvas=L.canvas({padding:.25});
      const stateLayer = L.geoJSON(states, {
        renderer:stateCanvas,
        style:{color:'#f59e0b',weight:2,fillOpacity:0},
        onEachFeature:function(f,layer){
          const p=f.properties||{};
          const name=p.state_name||p.state_code||'State';
          layer._ugamapStateLabel=name;
          layer.bindPopup('<b>'+name+'</b>');
        }
      }).addTo(map);

      let zipData=null;
      let zipLayer=L.layerGroup();
      let loadPromise=null;
      let renderTimer=null;
      let renderGeneration=0;
      let zipEnabled=true;
      const ZIPPER_MIN_ZOOM=12;
      const ZIPPER_LABEL_ZOOM=15;
      const MAX_VISIBLE_ZIPS=180;
      const palette=['#38bdf8','#22c55e','#facc15','#c084fc','#fb7185','#2dd4bf','#fb923c','#60a5fa','#a3e635','#f472b6'];
      const zipCanvas=L.canvas({padding:.2});

      if(!document.getElementById('ugamap-boundary-style')){
        const style=document.createElement('style');
        style.id='ugamap-boundary-style';
        style.textContent='.ugamap-zip-label{background:rgba(8,15,30,.88);color:#fff;border:1px solid rgba(56,189,248,.7);border-radius:4px;box-shadow:none;font-weight:800;font-size:9px;padding:1px 4px}.ugamap-zip-label:before{display:none}.ugamap-state-prefix{background:rgba(8,15,30,.92);color:#ffd166;border:1px solid rgba(245,158,11,.9);border-radius:7px;box-shadow:0 2px 8px rgba(0,0,0,.35);font-weight:800;font-size:11px;padding:3px 6px;white-space:nowrap}.ugamap-state-prefix:before{display:none}';
        document.head.appendChild(style);
      }

      async function ensureZipData(){
        if(zipData) return zipData;
        if(!loadPromise) loadPromise=safeGeoJson('/geography/zipper').then(function(data){
          zipData=data;
          (zipData.features||[]).forEach(function(f,i){
            f.__ugamapIndex=i;
            f.__ugamapBounds=featureBounds(f);
          });
          return zipData;
        });
        return loadPromise;
      }

      function clearZipLayer(){
        renderGeneration++;
        zipLayer.clearLayers();
        if(map.hasLayer(zipLayer)) map.removeLayer(zipLayer);
      }

      function scheduleRender(){
        clearTimeout(renderTimer);
        renderTimer=setTimeout(renderVisible,90);
      }

      async function renderVisible(){
        const generation=++renderGeneration;
        const zoom=map.getZoom();
        if(!zipEnabled || zoom<ZIPPER_MIN_ZOOM){ clearZipLayer(); updateStateLabels(); return; }

        const data=await ensureZipData();
        if(generation!==renderGeneration) return;
        const view=map.getBounds().pad(.08);
        const visible=[];
        for(const f of (data.features||[])){
          if(f.__ugamapBounds && f.__ugamapBounds.isValid() && view.intersects(f.__ugamapBounds)) visible.push(f);
          if(visible.length>=MAX_VISIBLE_ZIPS) break;
        }

        zipLayer.clearLayers();
        visible.forEach(function(f){
          const i=f.__ugamapIndex||0;
          const p=f.properties||{};
          const zip=fiveDigitId(p,i);
          const color=palette[i%palette.length];
          const one=L.geoJSON(f,{
            renderer:zipCanvas,
            style:{color:color,weight:.65,opacity:.75,fillColor:color,fillOpacity:.035},
            onEachFeature:function(_,layer){
              layer._ugamapZip=zip;
              const pop=Number(p.population||0);
              const district=p.district||'';
              layer.bindPopup('<b>ZIPPER '+zip+'</b>'+(pop?'<br>Estimated population: '+pop.toLocaleString():'')+(district?'<br>'+district:''));
              if(zoom>=ZIPPER_LABEL_ZOOM) layer.bindTooltip(zip,{permanent:true,direction:'center',className:'ugamap-zip-label',opacity:.92});
            }
          });
          one.addTo(zipLayer);
        });
        if(generation!==renderGeneration) return;
        if(!map.hasLayer(zipLayer)) zipLayer.addTo(map);
        updateStateLabels();
      }

      function updateStateLabels(){
        const zoom=map.getZoom();
        stateLayer.eachLayer(function(layer){
          const label=layer._ugamapStateLabel;
          if(!label)return;
          if(zoom<=9){
            if(!layer.getTooltip()) layer.bindTooltip(label,{permanent:true,direction:'center',className:'ugamap-state-prefix',opacity:.96});
          } else if(layer.getTooltip()) layer.unbindTooltip();
        });
      }

      const control=L.control.layers(null,{'State Boundaries':stateLayer,'5-digit ZIPPER':zipLayer},{collapsed:true,position:'topright'}).addTo(map);
      map.on('overlayadd',function(e){ if(e.layer===zipLayer){zipEnabled=true;scheduleRender();} });
      map.on('overlayremove',function(e){ if(e.layer===zipLayer){zipEnabled=false;clearZipLayer();} });
      map.on('zoomend moveend',scheduleRender);
      updateStateLabels();
      scheduleRender();

      const warm=function(){ensureZipData().catch(function(){});};
      if('requestIdleCallback' in window) requestIdleCallback(warm,{timeout:2500});
      else setTimeout(warm,1200);

      window.UGAMAP=window.UGAMAP||{};
      window.UGAMAP.boundaries={states:stateLayer,zips:zipLayer,updateLabels:scheduleRender,minZoom:ZIPPER_MIN_ZOOM,labelZoom:ZIPPER_LABEL_ZOOM,maxVisible:MAX_VISIBLE_ZIPS,control:control};
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