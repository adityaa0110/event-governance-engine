const BASE = '/api'

function authHeaders() {
  const token = localStorage.getItem('governance_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(options.headers || {}),
    },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  ready: () => request('/ready'),
  config: () => request('/config'),
  me: () => request('/me'),
  stats: () => request('/stats'),
  demoPrd: () => request('/demo/prd'),
  listEvents: (q, offset = 0, status = '') =>
    request(
      `/events?limit=50&offset=${offset}${q ? `&q=${encodeURIComponent(q)}` : ''}${status ? `&status=${encodeURIComponent(status)}` : ''}`,
    ),
  updateEvent: (name, payload) =>
    request(`/events/${encodeURIComponent(name)}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  getEvent: (name) => request(`/events/${encodeURIComponent(name)}`),
  versions: (name) => request(`/events/${encodeURIComponent(name)}/versions`),
  createEvent: (payload) => request('/events', { method: 'POST', body: JSON.stringify(payload) }),
  transition: (name, action, replacement, comment, expectedRevision) =>
    request(`/events/${encodeURIComponent(name)}/transitions`, {
      method: 'POST',
      body: JSON.stringify({ action, replacement, comment, expected_revision: expectedRevision }),
    }),
  diff: (name) => request(`/events/${encodeURIComponent(name)}/diff`),
  schema: (name) => request(`/events/${encodeURIComponent(name)}/schema`),
  types: (name, language) => request(`/events/${encodeURIComponent(name)}/types?language=${encodeURIComponent(language)}`),
  usages: (name) => request(`/events/${encodeURIComponent(name)}/usages`),
  queue: () => request('/queue'),
  notifications: () => request('/notifications?unread=true'),
  markNotification: (id) => request(`/notifications/${id}/read`, { method: 'POST' }),
  aiRuns: () => request('/ai-runs?limit=8'),
  validatePayload: (payload) => request('/validate/payload', { method: 'POST', body: JSON.stringify(payload) }),
  trackingFunctions: () => request('/tracking-functions'),
  addTrackingFunction: (payload) =>
    request('/tracking-functions', { method: 'POST', body: JSON.stringify(payload) }),
  decide: (payload) => request('/recommendations', { method: 'POST', body: JSON.stringify(payload) }),
  recommendations: () => request('/recommendations?limit=8'),
  generate: (requirement, platform = 'BROADBAND') =>
    request('/events/generate', {
      method: 'POST',
      body: JSON.stringify({ requirement, platform }),
    }),
  validate: (payload) =>
    request('/validate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listValidations: () => request('/validation?limit=8'),
  audit: () => request('/audit?limit=8'),
}
