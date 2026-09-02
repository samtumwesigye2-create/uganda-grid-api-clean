from pathlib import Path

# Patch backend with a same-origin Uganda news feed sourced server-side from Google News RSS.
main = Path('main.py')
s = main.read_text(encoding='utf-8')
if 'def uganda_trending_news' not in s:
    s = s.replace('import uuid\n', 'import uuid\nimport urllib.request\nimport xml.etree.ElementTree as ET\n', 1)
    marker = '\n\n@app.get("/stats")\ndef stats():'
    route = r'''

@app.get("/news/uganda")
def uganda_trending_news():
    """Same-origin proxy for Uganda headlines so the mobile UI does not
    depend on third-party browser CORS support."""
    rss_url = "https://news.google.com/rss/search?q=Uganda&hl=en-UG&gl=UG&ceid=UG:en"
    req = urllib.request.Request(
        rss_url,
        headers={"User-Agent": "Mozilla/5.0 UgandaNationalGrid/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            root = ET.fromstring(resp.read())
        items = []
        for node in root.findall('.//item')[:8]:
            title = (node.findtext('title') or '').strip()
            link = (node.findtext('link') or '').strip()
            pub_date = (node.findtext('pubDate') or '').strip()
            source_node = node.find('source')
            source = (source_node.text or '').strip() if source_node is not None else 'News'
            if title and link:
                items.append({"title": title, "url": link, "source": source, "published": pub_date})
        if not items:
            raise RuntimeError('No headlines returned')
        return {"count": len(items), "results": items}
    except Exception as exc:
        # Keep the UI useful even if the external feed is temporarily unavailable.
        return {
            "count": 3,
            "degraded": True,
            "results": [
                {"title": "Uganda news — BBC Africa", "url": "https://www.bbc.com/news/topics/cz4pr2gd85qt", "source": "BBC News", "published": ""},
                {"title": "Latest Uganda news", "url": "https://www.monitor.co.ug/uganda/news/national", "source": "Daily Monitor", "published": ""},
                {"title": "Uganda news and current affairs", "url": "https://www.newvision.co.ug/", "source": "New Vision", "published": ""},
            ],
        }
'''
    if marker not in s:
        raise SystemExit('stats marker not found in main.py')
    s = s.replace(marker, route + marker, 1)
    main.write_text(s, encoding='utf-8')

# Add a resilient frontend fallback that replaces only the failed Trending area.
index = Path('index.html')
h = index.read_text(encoding='utf-8')
if 'ugandaNewsFallbackV1' not in h:
    js = r'''
<script id="ugandaNewsFallbackV1">
(function(){
  let loading=false, loaded=false;
  const esc=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function findFailedNewsNode(){
    const all=[...document.querySelectorAll('div,p,span')];
    return all.find(el=>el.children.length===0 && /unable to load news/i.test((el.textContent||'').trim()));
  }
  async function repair(){
    if(loading||loaded)return;
    const node=findFailedNewsNode();
    if(!node)return;
    loading=true;
    try{
      const r=await fetch('/news/uganda',{cache:'no-store'});
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      const items=Array.isArray(d.results)?d.results:[];
      if(!items.length)throw new Error('No headlines');
      node.innerHTML=items.slice(0,6).map(x=>
        '<a class="newsItem" href="'+esc(x.url)+'" target="_blank" rel="noopener" style="display:block;margin:0 0 7px">'+
        '<div class="newsTitle">'+esc(x.title)+'</div>'+
        '<div class="newsSource">'+esc(x.source||'News')+'</div></a>'
      ).join('');
      node.style.color='inherit';
      loaded=true;
    }catch(e){
      node.textContent='News temporarily unavailable — tap More again to retry.';
    }finally{loading=false;}
  }
  const observer=new MutationObserver(()=>setTimeout(repair,0));
  observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['class','style']});
  document.addEventListener('click',()=>setTimeout(repair,120));
  window.addEventListener('load',()=>setTimeout(repair,500));
})();
</script>
'''
    if '</body>' not in h:
        raise SystemExit('body close not found in index.html')
    h = h.replace('</body>', js + '\n</body>', 1)
    index.write_text(h, encoding='utf-8')
