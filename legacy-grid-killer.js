(function(){
  if(!window.L||!L.map)return;
  const wrappedMap=L.map;

  function isLegacyGridLayer(layer){
    try{
      const p=layer&&layer.feature&&layer.feature.properties;
      if(!p)return false;
      const values=Object.values(p).map(v=>String(v==null?'':v));
      const id=String(p.grid_id||p.gridId||p.zone_id||p.zoneId||p.code||'');
      if(/^GZ-/i.test(id))return true;
      return values.some(v=>/^GZ-[A-Z0-9-]+$/i.test(v));
    }catch(_){return false;}
  }

  function suppressLegacyGrid(map){
    if(!map||map.__ugamapLegacyGridSuppression)return;
    map.__ugamapLegacyGridSuppression=true;

    function removeLegacy(layer){
      if(!layer)return;
      if(isLegacyGridLayer(layer)){
        setTimeout(()=>{try{if(map.hasLayer(layer))map.removeLayer(layer);}catch(_){}},0);
        return;
      }
      if(typeof layer.eachLayer==='function'){
        try{layer.eachLayer(child=>{
          if(isLegacyGridLayer(child)){
            try{layer.removeLayer(child);}catch(_){try{if(map.hasLayer(child))map.removeLayer(child);}catch(__){}}
          }
        });}catch(_){}
      }
    }

    map.on('layeradd',e=>removeLegacy(e.layer));
    setTimeout(()=>map.eachLayer(removeLegacy),0);
    setTimeout(()=>map.eachLayer(removeLegacy),500);
    setTimeout(()=>map.eachLayer(removeLegacy),2000);
    setTimeout(()=>map.eachLayer(removeLegacy),5000);
  }

  L.map=function(){
    const map=wrappedMap.apply(this,arguments);
    suppressLegacyGrid(map);
    return map;
  };
  Object.keys(wrappedMap).forEach(k=>{try{L.map[k]=wrappedMap[k];}catch(_){}});
})();
