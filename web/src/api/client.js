// OPC Platform API Client
const BASE = '/api/v1';

const token = () => localStorage.getItem('opc_token');
const refreshTokenValue = () => localStorage.getItem('opc_refresh_token');
const headers = () => {
  const h = { 'Content-Type': 'application/json' };
  const t = token();
  if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
};

/** 全局 429 回调 — 页面可覆盖此函数以自定义提示 UI */
let onRateLimited = (retryAfter, message) => {
  const sec = retryAfter || 60;
  alert(`操作太频繁了，请 ${Math.ceil(sec)} 秒后再试`);
};

/** 设置自定义 429 回调 (React 组件可用于 show toast) */
export function setRateLimitHandler(fn) {
  onRateLimited = fn;
}

// Token refresh state — avoids concurrent refresh attempts
let isRefreshing = false;
let refreshPromise = null;

/** Attempt to refresh the access token using the stored refresh token */
async function refreshToken() {
  const rt = refreshTokenValue();
  if (!rt) throw new Error('No refresh token');

  const res = await fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: rt }),
  });

  if (!res.ok) {
    clearTokens();
    throw new Error('Token refresh failed');
  }

  const data = await res.json();
  setToken(data.access_token);
  if (data.refresh_token) setRefreshToken(data.refresh_token);
  return data.access_token;
}

async function request(method, path, body, retry = true) {
  const opts = { method, headers: headers() };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);

  // 401 — attempt token refresh once, then retry
  if (res.status === 401 && retry) {
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = refreshToken().finally(() => {
        isRefreshing = false;
        refreshPromise = null;
      });
    }

    try {
      await refreshPromise;
      // Retry the original request with the fresh token
      return request(method, path, body, false);
    } catch (_e) {
      // Refresh failed — clear tokens and redirect to login
      clearTokens();
      window.location.href = '/login';
      throw _e;
    }
  }

  // 429 限流 — 提取 Retry-After 并回调
  if (res.status === 429) {
    const retryAfter = res.headers.get('Retry-After') || 60;
    let message = '请求过于频繁，请稍后再试';
    try {
      const errData = await res.json();
      message = errData?.detail || errData?.error?.message || message;
    } catch (_) {}
    onRateLimited(Number(retryAfter), message);
    throw new Error(message);
  }

  const data = await res.json();
  if (!res.ok) throw new Error(data.error?.message || res.statusText);
  return data;
}

export const api = {
  // Auth
  login: (tenant_slug, username, password) =>
    request('POST', '/auth/login', { tenant_slug, username, password }),
  me: () => request('GET', '/auth/me'),

  // Knowledge
  getDocuments: (params = {}) =>
    request('GET', `/knowledge/documents?${new URLSearchParams(params)}`),
  getDocument: (id) => request('GET', `/knowledge/documents/${id}`),
  deleteDocument: (id) => request('DELETE', `/knowledge/documents/${id}`),
  uploadDocument: (formData) => {
    const opts = { method: 'POST', headers: { Authorization: headers().Authorization }, body: formData };
    return fetch(`${BASE}/knowledge/upload`, opts).then(r => r.json());
  },
  uploadText: (title, content) => {
    const fd = new FormData();
    fd.append('title', title);
    fd.append('content', content);
    const opts = { method: 'POST', headers: { Authorization: headers().Authorization }, body: fd };
    return fetch(`${BASE}/knowledge/text`, opts).then(r => r.json());
  },
  askQuestion: (question, userRole = 'member') => {
    const fd = new FormData();
    fd.append('question', question);
    fd.append('top_k', '5');
    if (userRole) fd.append('user_role', userRole);
    const opts = { method: 'POST', headers: { Authorization: headers().Authorization }, body: fd };
    return fetch(`${BASE}/knowledge/ask`, opts).then(r => r.json());
  },
  getCategories: () => request('GET', '/knowledge/categories'),
  createCategory: (name, description) => {
    const fd = new FormData();
    fd.append('name', name);
    if (description) fd.append('description', description);
    const opts = { method: 'POST', headers: { Authorization: headers().Authorization }, body: fd };
    return fetch(`${BASE}/knowledge/categories`, opts).then(r => r.json());
  },
  getExpiringDocuments: () => request('GET', '/knowledge/documents/expiring'),
  renewDocument: (id) => {
    const fd = new FormData();
    const opts = { method: 'POST', headers: { Authorization: headers().Authorization }, body: fd };
    return fetch(`${BASE}/knowledge/documents/${id}/renew`, opts).then(r => r.json());
  },
  getStats: () => request('GET', '/knowledge/stats'),
  fulltextSearch: (q) => request('GET', `/knowledge/search?q=${encodeURIComponent(q)}`),

  // Social
  getPosts: (params = {}) =>
    request('GET', `/social/posts?${new URLSearchParams(params)}`),
  createPost: (content) => request('POST', '/social/posts', { content }),
  archivePost: (id, category, tags) => {
    const fd = new FormData();
    if (category) fd.append('category', category);
    if (tags) fd.append('tags', tags);
    const opts = { method: 'POST', headers: { Authorization: headers().Authorization }, body: fd };
    return fetch(`${BASE}/social/posts/${id}/archive-to-knowledge`, opts).then(r => r.json());
  },
  deletePost: (id) => request('DELETE', `/social/posts/${id}`),

  // Agent
  listAgents: () => request('GET', '/agent/list'),
  runAgent: (agentName, message, mode = 'single') =>
    request('POST', '/agent/run', { agent_name: agentName, message, mode }),

  // Device
  getDevices: () => request('GET', '/devices'),

  // Discover
  getFeed: (page = 1) => request('GET', `/discover/feed?page=${page}`),
  getNearby: (lat, lng) => request('GET', `/discover/nearby?lat=${lat}&lng=${lng}`),
  getBusinessCard: (userId) => request('GET', `/discover/users/${userId}/business-card`),

  // Ops
  getDashboard: () => request('GET', '/ops/dashboard'),
};

export const setToken = (t) => localStorage.setItem('opc_token', t);
export const setRefreshToken = (t) => localStorage.setItem('opc_refresh_token', t);
export const getRefreshToken = () => localStorage.getItem('opc_refresh_token');
export const clearTokens = () => {
  localStorage.removeItem('opc_token');
  localStorage.removeItem('opc_refresh_token');
};
export const clearToken = clearTokens; // backwards compatibility
export const isLoggedIn = () => !!token();
