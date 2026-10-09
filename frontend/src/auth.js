function base64Url(bytes) {
  return btoa(String.fromCharCode(...bytes))
    .replaceAll('+', '-')
    .replaceAll('/', '_')
    .replace(/=+$/g, '')
}

function randomString() {
  return base64Url(crypto.getRandomValues(new Uint8Array(32)))
}

async function challenge(verifier) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  return base64Url(new Uint8Array(digest))
}

export function can(principal, role) {
  const roles = new Set(principal?.roles || [])
  if (roles.has('admin')) return true
  const order = ['viewer', 'editor', 'approver']
  const needed = order.indexOf(role)
  if (needed === -1) return roles.has(role)
  return order.some((owned, index) => roles.has(owned) && index >= needed)
}

export async function beginLogin(config) {
  const discovery = await fetch(`${config.issuer.replace(/\/$/, '')}/.well-known/openid-configuration`)
  if (!discovery.ok) throw new Error('OIDC discovery failed')
  const metadata = await discovery.json()
  const verifier = randomString()
  const state = randomString()
  sessionStorage.setItem('oidc_verifier', verifier)
  sessionStorage.setItem('oidc_state', state)
  sessionStorage.setItem('oidc_token_endpoint', metadata.token_endpoint)
  sessionStorage.setItem('oidc_client_id', config.client_id)
  const url = new URL(metadata.authorization_endpoint)
  url.searchParams.set('client_id', config.client_id)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('scope', config.scopes || 'openid profile email')
  url.searchParams.set('redirect_uri', window.location.origin)
  url.searchParams.set('state', state)
  url.searchParams.set('code_challenge', await challenge(verifier))
  url.searchParams.set('code_challenge_method', 'S256')
  window.location.assign(url.toString())
}

export async function completeLogin() {
  const params = new URLSearchParams(window.location.search)
  const code = params.get('code')
  const state = params.get('state')
  if (!code) return false
  if (state !== sessionStorage.getItem('oidc_state')) throw new Error('OIDC state mismatch')
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    client_id: sessionStorage.getItem('oidc_client_id') || '',
    redirect_uri: window.location.origin,
    code_verifier: sessionStorage.getItem('oidc_verifier') || '',
  })
  const response = await fetch(sessionStorage.getItem('oidc_token_endpoint'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!response.ok) throw new Error('OIDC token exchange failed')
  const token = await response.json()
  localStorage.setItem('governance_token', token.access_token)
  window.history.replaceState({}, '', window.location.pathname)
  return true
}

export function logout() {
  localStorage.removeItem('governance_token')
}
