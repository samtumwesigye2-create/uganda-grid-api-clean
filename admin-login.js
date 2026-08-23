(function () {
  const STORAGE_KEY = "admin_passcode";

  function buildOverlay() {
    const overlay = document.createElement("div");
    overlay.id = "passcode-overlay";
    overlay.style.cssText = `
      position: fixed; inset: 0; background: #111827;
      display: flex; align-items: center; justify-content: center;
      z-index: 999999; font-family: system-ui, sans-serif;
    `;
    overlay.innerHTML = `
      <form id="passcode-form" style="
        background: #1f2937; padding: 32px 28px; border-radius: 12px;
        width: 280px; box-shadow: 0 10px 30px rgba(0,0,0,0.4);
      ">
        <h2 style="color:#f9fafb; margin:0 0 16px; font-size:18px;">Admin Login</h2>
        <input id="passcode-input" type="password" placeholder="Passcode"
          style="width:100%; padding:10px 12px; border-radius:8px; border:1px solid #374151;
                 background:#111827; color:#f9fafb; font-size:14px; box-sizing:border-box;"
          autofocus />
        <div id="passcode-error" style="color:#f87171; font-size:13px; margin-top:8px; min-height:16px;"></div>
        <button type="submit" style="
          margin-top:12px; width:100%; padding:10px; border:none; border-radius:8px;
          background:#2563eb; color:white; font-size:14px; font-weight:600; cursor:pointer;
        ">Unlock</button>
      </form>
    `;
    document.body.appendChild(overlay);

    const form = overlay.querySelector("#passcode-form");
    const input = overlay.querySelector("#passcode-input");
    const errorEl = overlay.querySelector("#passcode-error");

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      const candidate = input.value;
      errorEl.textContent = "Checking...";

      try {
        const check = await fetch(window.location.pathname, { headers: { "x-passcode": candidate } });
        if (check.status === 401) {
          errorEl.textContent = "Incorrect passcode";
          return;
        }
      } catch (err) {
        errorEl.textContent = "Could not reach server";
        return;
      }

      sessionStorage.setItem(STORAGE_KEY, candidate);
      overlay.remove();
      patchFetch(candidate);
    });
  }

  function patchFetch(passcode) {
    const originalFetch = window.fetch;
    window.fetch = function (input, init) {
      init = init || {};
      init.headers = Object.assign({}, init.headers, { "x-passcode": passcode });
      return originalFetch(input, init);
    };
  }

  const saved = sessionStorage.getItem(STORAGE_KEY);
  if (saved) {
    patchFetch(saved);
  } else {
    document.addEventListener("DOMContentLoaded", buildOverlay);
  }
})();
