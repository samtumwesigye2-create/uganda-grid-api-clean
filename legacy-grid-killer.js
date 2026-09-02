(function(){
  if(!window.L||!L.map)return;
  const wrappedMap=L.map;

  function textOfLayer(layer){
    try{
      const out=[];
      const p=layer&&layer.feature&&layer.feature.properties;
      if(p) Object.values(p).forEach(v=>out.push(String(v==null?'':v)));
      if(layer&&typeof layer.getTooltip==='function'){
        const t=layer.getTooltip();
        if(t&&typeof t.getContent==='function') out.push(String(t.getContent()||''));
      }
      if(layer&&typeof layer.getPopup==='function'){
        const p2=layer.getPopup();
        if(p2&&typeof p2.getContent==='function') out.push(String(p2.getContent()||''));
      }
      if(layer&&layer._tooltip&&layer._tooltip._content) out.push(String(layer._tooltip._content));
      if(layer&&layer._popup&&layer._popup._content) out.push(String(layer._popup._content));
      return out.join(' | ');
    }catch(_){return '';}
  }

  function isLegacyGridLayer(layer){
    const text=textOfLayer(layer);
    return /\bGZ-[A-Z0-9]+-[A-Z0-9-]+\b/i.test(text) || /\bGZ-[A-Z0-9-]+\b/i.test(text);
  }

  function suppressLegacyGrid(map){
    if(!map||map.__ugamapLegacyGridSuppression)return;
    map.__ugamapLegacyGridSuppression=true;

    function removeLegacy(layer,parent){
      if(!layer)return;
      if(isLegacyGridLayer(layer)){
        try{
          if(parent&&typeof parent.removeLayer==='function') parent.removeLayer(layer);
          else if(map.hasLayer(layer)) map.removeLayer(layer);
        }catch(_){}
        return;
      }
      if(typeof layer.eachLayer==='function'){
        try{
          const children=[];
          layer.eachLayer(child=>children.push(child));
          children.forEach(child=>removeLegacy(child,layer));
        }catch(_){}
      }
    }

    function sweep(){
      try{
        const layers=[];
        map.eachLayer(l=>layers.push(l));
        layers.forEach(l=>removeLegacy(l,null));
      }catch(_){}
    }

    map.on('layeradd',e=>setTimeout(()=>removeLegacy(e.layer,null),0));
    map.on('tooltipopen',e=>setTimeout(()=>removeLegacy(e.tooltip&&e.tooltip._source,null),0));
    map.on('popupopen',e=>setTimeout(()=>removeLegacy(e.popup&&e.popup._source,null),0));
    [0,150,500,1000,2000,4000,7000,12000].forEach(ms=>setTimeout(sweep,ms));
    map.on('zoomend moveend',()=>setTimeout(sweep,60));
  }

  L.map=function(){
    const map=wrappedMap.apply(this,arguments);
    suppressLegacyGrid(map);
    return map;
  };
  Object.keys(wrappedMap).forEach(k=>{try{L.map[k]=wrappedMap[k];}catch(_){}});
})();
