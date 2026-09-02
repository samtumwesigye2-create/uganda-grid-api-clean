// UGAMAP bootstrap: active 5-digit ZIPPER only. Retired GZ/ZIPPER-2 layers are suppressed.
// Release token intentionally changes whenever the production map bundle changes so browsers
// cannot reuse a retired grid script from an earlier Railway deployment.
(function(){
  const RELEASE='20260902-5digit-r1';
  try{
    if('caches' in window){
      caches.keys().then(keys=>Promise.all(keys.filter(k=>/^ugamap-/i.test(k)).map(k=>caches.delete(k)))).catch(()=>{});
    }
  }catch(_){}
  document.write('<script src="/boundaries.js?v='+RELEASE+'"><\/script>');
  document.write('<script src="/legacy-grid-killer.js?v='+RELEASE+'"><\/script>');
  document.write('<script src="/performance-layer.js?v=5-'+RELEASE+'"><\/script>');
  document.write('<script src="/app-core.js?v=9-'+RELEASE+'"><\/script>');
})();
