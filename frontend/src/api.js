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
  listEvents: (q, offset = 0) =>
    request(`/events?limit=50&offset=${offset}${q ? `&q=${encodeURIComponent(q)}` : ''}`),
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
