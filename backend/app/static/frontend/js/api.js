(() => {
  const base = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || "";
  async function request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(base + path, { ...options, headers, credentials: "include" });
    const type = response.headers.get("content-type") || "";
    const payload = type.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const message = (payload && payload.error) || `Request failed (${response.status})`;
      const error = new Error(message); error.status = response.status; throw error;
    }
    return payload;
  }
  window.API = {
    request,
    register: data => request("/api/auth/register", {method:"POST", body:JSON.stringify(data)}),
    login: data => request("/api/auth/login", {method:"POST", body:JSON.stringify(data)}),
    logout: () => request("/api/auth/logout", {method:"POST"}),
    me: () => request("/api/auth/me"),
    createLost: data => request("/api/reports/lost/", {method:"POST", body:data}),
    createFound: data => request("/api/reports/found/", {method:"POST", body:data}),
    myReports: () => request("/api/reports/mine"),
    matches: () => request("/api/matches"),
    match: id => request(`/api/matches/${id}`),
    notifications: () => request("/api/notifications"),
    recovery: () => request("/api/recovery-requests"),
    interest: id => request(`/api/matches/${id}/interest`,{method:"POST"}),
  };
})();