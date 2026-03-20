// ──────────────────────────────────────────────────────────────
// api.js  —  shared fetch helper + auth utilities
// API_BASE is set after deploy by updating this file with the
// actual API Gateway URL from `terraform output api_url`
// ──────────────────────────────────────────────────────────────

const API_BASE = window.API_BASE || localStorage.getItem("api_url") || "https://4s03l5ifkk.execute-api.us-east-1.amazonaws.com";

function getToken() {
  return localStorage.getItem("token");
}

function getUser() {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (payload.exp * 1000 < Date.now()) {
      localStorage.removeItem("token");
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

function requireAuth() {
  if (!getUser()) {
    window.location.href = "Login.html";
    return false;
  }
  return true;
}

function logout() {
  localStorage.removeItem("token");
  window.location.href = "Login.html";
}

async function apiCall(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const opts = { method, headers };
  if (body !== undefined) opts.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

const api = {
  signup: (name, email, password) =>
    apiCall("POST", "/auth/signup", { name, email, password }),
  login: (email, password) =>
    apiCall("POST", "/auth/login", { email, password }),
  products: () => apiCall("GET", "/products"),
  getCart: () => apiCall("GET", "/cart"),
  addToCart: (productId, quantity = 1) =>
    apiCall("POST", "/cart", { productId, quantity }),
  removeFromCart: (productId) =>
    apiCall("DELETE", `/cart/${productId}`),
  checkout: () => apiCall("POST", "/orders"),
  getOrders: () => apiCall("GET", "/orders"),
};
