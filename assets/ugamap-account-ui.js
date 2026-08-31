(() => {
  const TOKEN_KEY = 'ugamap_account_token_v1';
  let currentUser = null;

  function token() { return localStorage.getItem(TOKEN_KEY) || ''; }
  function setToken(v) { if (v) localStorage.setItem(TOKEN_KEY, v); else localStorage.removeItem(TOKEN_KEY); }
  function authHeaders() { const t = token(); return t ? { Authorization: 'Bearer ' + t } : {}; }
  function form(data) { const x = new URLSearchParams(); Object.entries(data).forEach(([k,v]) => { if (v !== undefined && v !== null) x.set(k, v); }); return x; }
  function esc(v) { return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  function style() {
    if (document.getElementById('ugAcctStyle')) return;
    const s = document.createElement('style'); s.id='ugAcctStyle'; s.textContent=`
      #ugAcctBtn{position:fixed;right:14px;top:14px;z-index:9500;border:1px solid #334155;background:#111827;color:#fff;border-radius:999px;padding:9px 13px;font:600 13px system-ui;box-shadow:0 6px 18px #0005}
      #ugAcctModal{position:fixed;inset:0;z-index:12000;background:#0009;display:none;align-items:center;justify-content:center;padding:16px}
      #ugAcctCard{width:min(430px,100%);max-height:88vh;overflow:auto;background:#0f172a;color:#e5e7eb;border:1px solid #334155;border-radius:16px;padding:16px;font-family:system-ui}
      #ugAcctCard h3{margin:0 0 12px;font-size:18px} #ugAcctCard input{width:100%;padding:11px;border-radius:9px;border:1px solid #334155;background:#111827;color:#fff;margin:6px 0;font-size:16px}
      #ugAcctCard button{padding:10px 12px;border:0;border-radius:9px;background:#2563eb;color:white;font-weight:700;margin:6px 6px 0 0} #ugAcctCard button.secondary{background:#334155} #ugAcctCard button.danger{background:#b91c1c}
      #ugAcctMsg{font-size:13px;margin:8px 0;min-height:18px}.ugAcctTabs{display:flex;gap:8px;margin-bottom:10px}.ugAcctTabs button{flex:1}.ugAcctSection{display:none}.ugAcctSection.active{display:block}.ugAcctSmall{font-size:12px;color:#94a3b8}.ugAcctRow{display:grid;grid-template-columns:1fr 1fr;gap:8px}
      @media(max-width:420px){.ugAcctRow{grid-template-columns:1fr}}
    `; document.head.appendChild(s);
  }

  function ensureUI() {
    style();
    if (!document.getElementById('ugAcctBtn')) {
      const b=document.createElement('button'); b.id='ugAcctBtn'; b.type='button'; b.textContent='Account'; b.onclick=open; document.body.appendChild(b);
    }
    if (document.getElementById('ugAcctModal')) return;
    const m=document.createElement('div'); m.id='ugAcctModal'; m.innerHTML=`<div id="ugAcctCard">
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:center"><h3>UGAMAP Account</h3><button id="ugAcctClose" class="secondary" type="button">Close</button></div>
      <div id="ugAcctMsg"></div>
      <div id="ugAcctGuest">
        <div class="ugAcctTabs"><button type="button" data-tab="login">Login</button><button type="button" class="secondary" data-tab="signup">Sign Up</button></div>
        <section id="ugLogin" class="ugAcctSection active"><input id="ugLoginEmail" type="email" autocomplete="email" placeholder="Email"><input id="ugLoginPassword" type="password" autocomplete="current-password" placeholder="Password"><button id="ugLoginBtn" type="button">Login</button></section>
        <section id="ugSignup" class="ugAcctSection"><input id="ugSignupEmail" type="email" autocomplete="email" placeholder="Email"><input id="ugSignupPhone" type="tel" autocomplete="tel" placeholder="Phone number"><input id="ugSignupAddress" type="text" autocomplete="street-address" placeholder="Address"><input id="ugSignupPassword" type="password" autocomplete="new-password" placeholder="Password (8+ characters)"><button id="ugSignupBtn" type="button">Create Account</button></section>
      </div>
      <div id="ugAcctProfile" style="display:none">
        <div class="ugAcctSmall">Signed in as</div><div id="ugAcctIdentity" style="font-weight:700;margin-bottom:10px"></div>
        <input id="ugProfileEmail" type="email" placeholder="Email"><input id="ugProfilePhone" type="tel" placeholder="Phone number"><input id="ugProfileAddress" type="text" placeholder="Address"><button id="ugSaveProfile" type="button">Save Profile</button>
        <hr style="border:0;border-top:1px solid #334155;margin:16px 0"><div class="ugAcctSmall">Change password</div><input id="ugCurrentPassword" type="password" placeholder="Current password"><input id="ugNewPassword" type="password" placeholder="New password"><button id="ugChangePassword" type="button">Change Password</button>
        <hr style="border:0;border-top:1px solid #334155;margin:16px 0"><button id="ugLogout" class="danger" type="button">Logout</button>
      </div>
    </div>`;
    document.body.appendChild(m);
    m.addEventListener('click', e => { if (e.target === m) close(); });
    document.getElementById('ugAcctClose').onclick=close;
    m.querySelectorAll('[data-tab]').forEach(btn => btn.onclick=()=>{
      const login=btn.dataset.tab==='login'; document.getElementById('ugLogin').classList.toggle('active',login); document.getElementById('ugSignup').classList.toggle('active',!login); m.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('secondary',x!==btn)); setMsg('');
    });
    document.getElementById('ugLoginBtn').onclick=login;
    document.getElementById('ugSignupBtn').onclick=signup;
    document.getElementById('ugSaveProfile').onclick=saveProfile;
    document.getElementById('ugChangePassword').onclick=changePassword;
    document.getElementById('ugLogout').onclick=logout;
  }

  function setMsg(text, bad=false){const e=document.getElementById('ugAcctMsg'); if(e){e.textContent=text||'';e.style.color=bad?'#fca5a5':'#86efac';}}
  function close(){const m=document.getElementById('ugAcctModal');if(m)m.style.display='none';}
  async function open(){ensureUI();document.getElementById('ugAcctModal').style.display='flex';await refreshUser();}
  function render(){const guest=document.getElementById('ugAcctGuest'),profile=document.getElementById('ugAcctProfile'),btn=document.getElementById('ugAcctBtn'); if(!guest)return; const signed=!!currentUser;guest.style.display=signed?'none':'block';profile.style.display=signed?'block':'none';btn.textContent=signed?'Profile':'Account';if(signed){document.getElementById('ugAcctIdentity').textContent=currentUser.email||currentUser.id;document.getElementById('ugProfileEmail').value=currentUser.email||'';document.getElementById('ugProfilePhone').value=currentUser.phone||'';document.getElementById('ugProfileAddress').value=currentUser.address||'';}}
  async function api(path,opt={}){const r=await fetch(path,opt);let d={};try{d=await r.json();}catch(_){ }if(!r.ok)throw new Error(d.detail||('HTTP '+r.status));return d;}
  async function refreshUser(){if(!token()){currentUser=null;render();return;}try{currentUser=await api('/account/me',{headers:authHeaders()});render();}catch(e){setToken('');currentUser=null;render();setMsg('Session expired. Please log in again.',true);}}
  async function login(){setMsg('Signing in...');try{const d=await api('/account/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:form({email:document.getElementById('ugLoginEmail').value.trim(),password:document.getElementById('ugLoginPassword').value})});setToken(d.token);currentUser=d.user;render();setMsg('Logged in.');}catch(e){setMsg(e.message,true);}}
  async function signup(){setMsg('Creating account...');try{const d=await api('/account/signup',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:form({email:document.getElementById('ugSignupEmail').value.trim(),phone:document.getElementById('ugSignupPhone').value.trim(),address:document.getElementById('ugSignupAddress').value.trim(),password:document.getElementById('ugSignupPassword').value})});setToken(d.token);currentUser=d.user;render();setMsg('Account created.');}catch(e){setMsg(e.message,true);}}
  async function saveProfile(){setMsg('Saving...');try{currentUser=await api('/account/me',{method:'PUT',headers:{...authHeaders(),'Content-Type':'application/x-www-form-urlencoded'},body:form({email:document.getElementById('ugProfileEmail').value.trim(),phone:document.getElementById('ugProfilePhone').value.trim(),address:document.getElementById('ugProfileAddress').value.trim()})});render();setMsg('Profile saved permanently.');}catch(e){setMsg(e.message,true);}}
  async function changePassword(){setMsg('Changing password...');try{await api('/account/password',{method:'POST',headers:{...authHeaders(),'Content-Type':'application/x-www-form-urlencoded'},body:form({current_password:document.getElementById('ugCurrentPassword').value,new_password:document.getElementById('ugNewPassword').value})});setToken('');currentUser=null;render();setMsg('Password changed. Please log in again.');}catch(e){setMsg(e.message,true);}}
  async function logout(){try{if(token())await api('/account/logout',{method:'POST',headers:authHeaders()});}catch(_){ }setToken('');currentUser=null;render();setMsg('Logged out.');}

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{ensureUI();refreshUser();});else{ensureUI();refreshUser();}
})();