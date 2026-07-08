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

const authHeaders = () => {
  const t = token();
  return t ? { Authorization: `Bearer ${t}` } : {};
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
      return request(method, path, body, false);
    } catch (_e) {
      clearTokens();
      window.location.href = '/login';
      throw _e;
    }
  }

  // 429 限流
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

// Form-encoded request (no JSON body, no Content-Type header)
async function requestForm(method, path, formData) {
  const opts = { method, headers: authHeaders(), body: formData };
  const res = await fetch(`${BASE}${path}`, opts);

  if (res.status === 401) {
    try {
      await refreshToken();
      opts.headers = authHeaders();
      const retryRes = await fetch(`${BASE}${path}`, opts);
      if (!retryRes.ok) throw new Error(retryRes.statusText);
      return retryRes.json();
    } catch (_e) {
      clearTokens();
      window.location.href = '/login';
      throw _e;
    }
  }

  if (res.status === 429) {
    const retryAfter = res.headers.get('Retry-After') || 60;
    onRateLimited(Number(retryAfter), '请求过于频繁');
    throw new Error('Rate limited');
  }

  const data = await res.json();
  if (!res.ok) throw new Error(data.error?.message || res.statusText);
  return data;
}

export const api = {
  // ========== Auth ==========
  login: (tenant_slug, username, password) =>
    request('POST', '/auth/login', { tenant_slug, username, password }),
  register: (data) =>
    request('POST', '/auth/register', data),
  me: () => request('GET', '/auth/me'),
  refresh: (refreshToken) =>
    request('POST', '/auth/refresh', { refresh_token: refreshToken }),
  logout: async () => {
    try { await request('POST', '/auth/logout'); } catch (_) { /* 即使失败也要清本地 */ }
    clearTokens();
  },

  // ========== Knowledge ==========
  getDocuments: (params = {}) =>
    request('GET', `/knowledge/documents?${new URLSearchParams(params)}`),
  getDocument: (id) => request('GET', `/knowledge/documents/${id}`),
  deleteDocument: (id) => request('DELETE', `/knowledge/documents/${id}`),
  uploadDocument: (formData) => requestForm('POST', '/knowledge/upload', formData),
  uploadText: (title, content) => {
    const fd = new FormData();
    fd.append('title', title);
    fd.append('content', content);
    return requestForm('POST', '/knowledge/text', fd);
  },
  askQuestion: (question, userRole = 'member') => {
    const fd = new FormData();
    fd.append('question', question);
    fd.append('top_k', '5');
    if (userRole) fd.append('user_role', userRole);
    return requestForm('POST', '/knowledge/ask', fd);
  },
  getCategories: () => request('GET', '/knowledge/categories'),
  createCategory: (name, description) => {
    const fd = new FormData();
    fd.append('name', name);
    if (description) fd.append('description', description);
    return requestForm('POST', '/knowledge/categories', fd);
  },
  getExpiringDocuments: () => request('GET', '/knowledge/documents/expiring'),
  renewDocument: (id) => requestForm('POST', `/knowledge/documents/${id}/renew`, new FormData()),
  getStats: () => request('GET', '/knowledge/stats'),
  fulltextSearch: (q) => request('GET', `/knowledge/search?q=${encodeURIComponent(q)}`),

  // ========== Social ==========
  getPosts: (params = {}) =>
    request('GET', `/social/posts?${new URLSearchParams(params)}`),
  createPost: (content, visibility = 'public') =>
    request('POST', '/social/posts', { content, visibility }),
  deletePost: (id) => request('DELETE', `/social/posts/${id}`),
  archivePost: (id, category, tags) => {
    const fd = new FormData();
    if (category) fd.append('category', category);
    if (tags) fd.append('tags', tags);
    return requestForm('POST', `/social/posts/${id}/archive-to-knowledge`, fd);
  },

  // Social — comments
  getComments: (postId) => request('GET', `/social/posts/${postId}/comments`),
  createComment: (postId, content) => {
    const fd = new FormData();
    fd.append('content', content);
    return requestForm('POST', `/social/posts/${postId}/comments`, fd);
  },
  likeComment: (commentId) => request('POST', `/social/comments/${commentId}/like`),

  // Social — likes
  likePost: (postId) => request('POST', `/social/posts/${postId}/like`),
  unlikePost: (postId) => request('DELETE', `/social/posts/${postId}/like`),

  // Social — follow & friends
  followUser: (userId) => request('POST', `/social/users/${userId}/follow`),
  getFriends: () => request('GET', '/social/friends'),
  sendFriendRequest: (friendId) =>
    request('POST', '/social/friends/request', { friend_id: friendId }),
  acceptFriend: (id) => request('POST', `/social/friends/${id}/accept`),

  // ========== Agent ==========
  listAgents: () => request('GET', '/agent/list'),
  runAgent: (agentName, message, mode = 'single') =>
    request('POST', '/agent/run', { agent_name: agentName, message, mode }),

  // ========== Skills ==========
  getSkills: () => request('GET', '/skills'),
  executeSkill: (skillName, parameters = {}) =>
    request('POST', '/skills/execute', { skill_name: skillName, parameters }),

  // ========== Devices ==========
  getDevices: () => request('GET', '/devices'),
  registerDevice: (data) => requestForm('POST', '/devices', data),
  updateDeviceStatus: (id, status) => {
    const fd = new FormData();
    fd.append('status', status);
    return requestForm('PATCH', `/devices/${id}/status`, fd);
  },

  // ========== Discover ==========
  getFeed: (page = 1) => request('GET', `/discover/feed?page=${page}`),
  getNearby: (lat, lng) => request('GET', `/discover/nearby?lat=${lat}&lng=${lng}`),
  getBusinessCard: (userId) => request('GET', `/discover/users/${userId}/business-card`),
  getMyStatus: () => request('GET', '/discover/users/me/status'),
  updateMyStatus: (data) => {
    const fd = new FormData();
    if (data.status_text) fd.append('status_text', data.status_text);
    if (data.mood) fd.append('mood', data.mood);
    return requestForm('PATCH', '/discover/users/me/status', fd);
  },

  // ========== Ops ==========
  getDashboard: () => request('GET', '/ops/dashboard'),

  // ========== Schedule ==========
  getScheduleStatus: () => request('GET', '/schedule/status'),
  runDailyTasks: () => request('POST', '/schedule/run-daily'),

  // ========== Notifications ==========
  getNotifications: () => request('GET', '/notifications'),
  getUnreadCount: () => request('GET', '/notifications/unread-count'),
  markRead: (id) => request('PATCH', `/notifications/${id}/read`),
  markAllRead: () => request('POST', '/notifications/read-all'),

  // ========== Conversations ==========
  getConversations: () => request('GET', '/conversations'),
  getMessages: (convId) => request('GET', `/conversations/${convId}/messages`),

  // ========== Settings ==========
  getLLMSettings: () => request('GET', '/settings/llm'),
  updateLLMSettings: (data) => request('POST', '/settings/llm', data),

  // ========== Search ==========
  search: (query, page = 1, pageSize = 10) =>
    request('POST', '/search', { query, page, page_size: pageSize }),
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

// Re-export for convenience
export { token, authHeaders };
