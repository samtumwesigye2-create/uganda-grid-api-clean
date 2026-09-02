(function(){
  const nativeFetch = window.fetch.bind(window);

  function fiveDigit(v){ return /^\d{5}$/.test(String(v || '').trim()); }

  async function lookup(code){
    const r = await nativeFetch('/zipper/lookup/' + encodeURIComponent(code), {cache:'no-store'});
    if(!r.ok) return null;
    return await r.json();
  }

  window.fetch = async function(input, init){
    try{
      const raw = typeof input === 'string' ? input : (input && input.url) || '';
      const url = new URL(raw, location.origin);

      if(url.origin === location.origin && url.pathname === '/search'){
        const q = url.searchParams.get('q') || '';
        if(fiveDigit(q)){
          const item = await lookup(q.trim());
          return new Response(JSON.stringify({count:item?1:0,results:item?[item]:[]}), {
            status:200,
            headers:{'Content-Type':'application/json'}
          });
        }
      }

      if(url.hostname === 'photon.komoot.io' && url.pathname === '/api/'){
        const q = url.searchParams.get('q') || '';
        if(fiveDigit(q)){
          const item = await lookup(q.trim());
          const features = item ? [{
            type:'Feature',
            geometry:{type:'Point',coordinates:[item.longitude,item.latitude]},
            properties:{
              name:'ZIPPER ' + item.zipper_id,
              city:item.district || '',
              state:item.state_code || '',
              country:'Uganda'
            }
          }] : [];
          return new Response(JSON.stringify({type:'FeatureCollection',features:features}), {
            status:200,
            headers:{'Content-Type':'application/json'}
          });
        }
      }
    }catch(_){ }
    return nativeFetch(input, init);
  };
})();
