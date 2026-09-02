// UGAMAP bootstrap: active 5-digit ZIPPER only.
(function(){
  const RELEASE='20260902-5digit-r3';
  try{
    if('caches' in window){
      caches.keys().then(keys=>Promise.all(keys.filter(k=>/^ugamap-/i.test(k)).map(k=>caches.delete(k)))).catch(()=>{});
    }
  }catch(_){}
  document.write('<script src="/boundaries.js?v='+RELEASE+'"><\/script>');
  document.write('<script src="/performance-layer.js?v=5-'+RELEASE+'"><\/script>');
  document.write('<script src="/app-core.js?v=9-'+RELEASE+'"><\/script>');
})();
