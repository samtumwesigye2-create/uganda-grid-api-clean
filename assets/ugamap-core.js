(() => {
  const API_BASE = "";

  async function request(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: "application/json", ...(options.headers || {}) },
      ...options,
    });

    let body = null;
    try {
      body = await response.json();
    } catch (_) {
      body = null;
    }

    if (!response.ok) {
      const message = body?.detail || body?.message || "UGAMAP service unavailable";
      const error = new Error(message);
      error.status = response.status;
      error.body = body;
      throw error;
    }
    return body;
  }

  const UGAMAPCore = {
    status: () => request("/core/status"),
    search: (query, limit = 20) => request(`/core/search?q=${encodeURIComponent(query)}&limit=${limit}`),
    address: (gridId) => request(`/core/address/${encodeURIComponent(gridId)}`),
    location: (lat, lon) => request(`/core/location?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`),
    reports: () => request("/core/reports"),
  };

  window.UGAMAPCore = UGAMAPCore;
})();
