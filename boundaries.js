(function () {
  if (!window.L) return;

  const originalMap = L.map;
  let initialized = false;

  function installRouteBranding() {
    const logo = document.querySelector('.mapHeaderLogo');
    if (!logo) return;
    const originalSrc = logo.getAttribute('src') || '';
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

  const API_BASES = (() => {
    const out = [];
    if (location.protocol && location.protocol.indexOf('http') === 0) out.push(location.origin);
    out.push('https://uganda-grid-api-clean-production.up.railway.app');
    return Array.from(new Set(out));
  })();

  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

  async function getJson(path) {
    let lastError = null;
    for (let attempt = 0; attempt < 4; attempt++) {
      for (const base of API_BASES) {
        try {
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), 45000);
          const r = await fetch(base + path, {headers:{Accept:'application/json'},cache:'no-store',signal:controller.signal});
          clearTimeout(timer);
          if (!r.ok) throw new Error(path+' returned HTTP '+r.status);
          return await r.json();
        } catch (e) { lastError = e; }
      }
      await wait(1200 * Math.pow(2, attempt));
    }
    throw lastError || new Error(path+' unavailable');
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
      const [states,zips] = await Promise.all([
        safeGeoJson('/geography/states'),
        safeGeoJson('/geography/zipper')
      ]);

      const stateLayer = L.geoJSON(states, {
        style:{color:'#f59e0b',weight:2.5,fillColor:'#f59e0b',fillOpacity:.01},
        onEachFeature:function(f,layer){
          const p=f.properties||{};
          const name=p.state_name||p.state_code||'State';
          layer.bindPopup('<b>'+name+'</b><br>State: '+(p.state_code||''));
          layer._ugamapStateLabel=name;
        }
      });

      const palette=['#38bdf8','#22c55e','#facc15','#c084fc','#fb7185','#2dd4bf','#fb923c','#60a5fa','#a3e635','#f472b6'];
      const zipLayer = L.geoJSON(zips, {
        style:function(f){
          const zip=String((f.properties||{}).zipper_id||(f.properties||{}).zip_code||'');
          const n=Number(zip.slice(-2))||1;
          const color=palette[(n-1)%palette.length];
          return {color:color,weight:1,fillColor:color,fillOpacity:.10};
        },
        onEachFeature:function(f,layer){
          const p=f.properties||{};
          const zip=String(p.zipper_id||p.zip_code||'').padStart(5,'0');
          const pop=Number(p.population||0);
          const district=p.district||'';
          layer.bindPopup('<b>ZIP '+zip+'</b><br>Population-balanced ZIPPER zone'+(pop?'<br>Estimated population: '+pop.toLocaleString():'')+(district?'<br>'+district:'')+(p.density_class?'<br><small>'+p.density_class+' allocation</small>':''));
          layer._ugamapZip=zip;
        }
      });

      if(!document.getElementById('ugamap-boundary-style')){
        const style=document.createElement('style');
        style.id='ugamap-boundary-style';
        style.textContent='.ugamap-zip-label{background:rgba(8,15,30,.86);color:#fff;border:1px solid rgba(255,255,255,.35);border-radius:5px;box-shadow:none;font-weight:800;font-size:10px;padding:2px 4px}.ugamap-zip-label:before{display:none}.ugamap-state-prefix{background:rgba(8,15,30,.92);color:#ffd166;border:1px solid rgba(245,158,11,.9);border-radius:7px;box-shadow:0 2px 8px rgba(0,0,0,.35);font-weight:800;font-size:11px;padding:3px 6px;white-space:nowrap}.ugamap-state-prefix:before{display:none}';
        document.head.appendChild(style);
      }

      function syncLabels(){
        const zoom=map.getZoom();
        zipLayer.eachLayer(function(layer){
          const zip=layer._ugamapZip;
          if(!zip)return;
          if(zoom>=13){
            if(!layer.getTooltip())layer.bindTooltip(zip,{permanent:true,direction:'center',className:'ugamap-zip-label',opacity:.92});
            layer.openTooltip();
          }else if(layer.getTooltip()){
            layer.unbindTooltip();
          }
        });
        stateLayer.eachLayer(function(layer){
          const label=layer._ugamapStateLabel;
          if(!label)return;
          if(zoom<=9){
            if(!layer.getTooltip())layer.bindTooltip(label,{permanent:true,direction:'center',className:'ugamap-state-prefix',opacity:.96});
            layer.openTooltip();
          }else if(layer.getTooltip()){
            layer.unbindTooltip();
          }
        });
      }

      async function recoverZipLayer(){
        if(zipLayer.getLayers().length) return;
        try{
          const fresh=await getJson('/geography/zipper');
          if(fresh&&Array.isArray(fresh.features)&&fresh.features.length){
            zipLayer.clearLayers();
            zipLayer.addData(fresh);
            syncLabels();
          }
        }catch(e){console.error('ZIPPER layer recovery failed:',e);}
      }

      L.control.layers(null,{
        'State Boundaries':stateLayer,
        'ZIPPER Zones':zipLayer
      },{collapsed:true,position:'topright'}).addTo(map);

      stateLayer.addTo(map);
      zipLayer.addTo(map);
      syncLabels();
      map.on('zoomend moveend',syncLabels);
      setTimeout(syncLabels,500);
      setTimeout(recoverZipLayer,3000);
      setTimeout(recoverZipLayer,10000);

      window.UGAMAP=window.UGAMAP||{};
      window.UGAMAP.boundaries={states:stateLayer,zips:zipLayer,updateLabels:syncLabels,recover:recoverZipLayer};
    } catch(e){
      initialized=false;
      console.error('Boundary layers unavailable:',e);
      setTimeout(function(){initializeBoundaries(map);},3000);
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
