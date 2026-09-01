(() => {
  const KEY='ugamap_language_v1';
  const languages={
    en:{name:'English',code:'en'},
    lg:{name:'Luganda',code:'lg'},
    sw:{name:'Kiswahili',code:'sw'},
    ach:{name:'Acholi',code:'ach'},
    nyn:{name:'Runyankole',code:'nyn'},
    teo:{name:'Ateso',code:'teo'},
    lgg:{name:'Lugbara',code:'lgg'}
  };
  const t={
    en:{title:'Uganda National Grid',subtitle:'Search, route and navigate across Uganda',start:'Start location',destination:'Destination',navigate:'Navigate',myLocation:'My location',driving:'Driving',walking:'Walking',cycling:'Cycling',flight:'Flight',language:'Language',choose:'Choose language',close:'Close'},
    lg:{title:'Uganda National Grid',subtitle:'Noonya, kola olugendo era olagirire mu Uganda',start:'Wotandikira',destination:'Gy’ogenda',navigate:'Lagirirwa',myLocation:'Wendi',driving:'Okuvuga',walking:'Okutambula',cycling:'Eggaali',flight:'Ennyonyi',language:'Olulimi',choose:'Londa olulimi',close:'Ggalawo'},
    sw:{title:'Uganda National Grid',subtitle:'Tafuta, panga njia na uabiri kote Uganda',start:'Mahali pa kuanzia',destination:'Unakoenda',navigate:'Abiri',myLocation:'Mahali nilipo',driving:'Kuendesha',walking:'Kutembea',cycling:'Baiskeli',flight:'Ndege',language:'Lugha',choose:'Chagua lugha',close:'Funga'},
    ach:{language:'Leb',choose:'Yer leb',close:'Lor'},
    nyn:{language:'Orurimi',choose:'Toorana orurimi',close:'Gara'},
    teo:{language:'Aŋajep',choose:'Sio aŋajep',close:'Kony'},
    lgg:{language:'Dri',choose:'Eri dri',close:'Esi'}
  };
  let current=localStorage.getItem(KEY)||'en';if(!languages[current])current='en';
  const q=s=>document.querySelector(s);const by=id=>document.getElementById(id);
  function text(key){return (t[current]&&t[current][key])||(t.en[key])||key;}
  function setText(sel,value){const e=q(sel);if(e)e.textContent=value;}
  function apply(){
    document.documentElement.lang=current;localStorage.setItem(KEY,current);
    setText('header h1',text('title'));setText('header p',text('subtitle'));
    const sl=q('label[for="start"]'),dl=q('label[for="dest"]');if(sl)sl.textContent=text('start');if(dl)dl.textContent=text('destination');
    setText('#navigate .navSub',text('navigate'));setText('#myLocation',text('myLocation'));
    const mode=by('mode');if(mode&&mode.options.length>=4){mode.options[0].text='🚘 '+text('driving');mode.options[1].text='🚶 '+text('walking');mode.options[2].text='🚴 '+text('cycling');mode.options[3].text='✈️ '+text('flight');}
    const b=by('ugLangMenuBtn');if(b)b.textContent='🌐 '+text('language')+' · '+languages[current].name;
    const h=by('ugLangTitle');if(h)h.textContent=text('choose');const c=by('ugLangClose');if(c)c.textContent=text('close');
    window.dispatchEvent(new CustomEvent('ugamap:languagechange',{detail:{language:current}}));
  }
  function ensure(){
    if(!by('ugLangStyle')){const s=document.createElement('style');s.id='ugLangStyle';s.textContent='#ugLangModal{position:fixed;inset:0;z-index:12500;background:#0009;display:none;align-items:center;justify-content:center;padding:16px}#ugLangCard{width:min(420px,100%);background:#0f172a;color:#e5e7eb;border:1px solid #334155;border-radius:16px;padding:16px;font-family:system-ui}#ugLangGrid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}#ugLangGrid button,#ugLangClose{padding:11px;border:1px solid #334155;border-radius:9px;background:#1e293b;color:#fff;font-weight:700}#ugLangGrid button.active{background:#2563eb;border-color:#2563eb}';document.head.appendChild(s);}
    if(!by('ugLangModal')){const m=document.createElement('div');m.id='ugLangModal';m.innerHTML='<div id="ugLangCard"><div style="display:flex;align-items:center;justify-content:space-between;gap:8px"><h3 id="ugLangTitle" style="margin:0">Choose language</h3><button id="ugLangClose" type="button">Close</button></div><div id="ugLangGrid"></div></div>';document.body.appendChild(m);m.onclick=e=>{if(e.target===m)m.style.display='none'};by('ugLangClose').onclick=()=>m.style.display='none';const g=by('ugLangGrid');Object.entries(languages).forEach(([code,x])=>{const b=document.createElement('button');b.type='button';b.dataset.lang=code;b.textContent=x.name;b.onclick=()=>{current=code;g.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x.dataset.lang===current));apply();m.style.display='none'};g.appendChild(b);});}
    const accountMenu=by('ugAcctMenu');if(accountMenu&&!by('ugLangMenuBtn')){const b=document.createElement('button');b.id='ugLangMenuBtn';b.type='button';b.textContent='🌐 Language';b.onclick=e=>{e.stopPropagation();accountMenu.classList.remove('open');const m=by('ugLangModal');m.style.display='flex';by('ugLangGrid').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x.dataset.lang===current));apply();};accountMenu.appendChild(b);}
    apply();
  }
  const timer=setInterval(()=>{ensure();if(by('ugLangMenuBtn'))clearInterval(timer)},250);if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ensure);else ensure();
  window.UGAMAPLanguage={get:()=>current,set:code=>{if(languages[code]){current=code;apply()}},languages};
})();