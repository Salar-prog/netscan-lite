import type {
  AvailableResponse,
  Group,
  GroupDetail,
  ImportResponse,
  IPAddress,
  ScanResponse,
  Stats,
  TokenResponse,
  WSMessage,
} from './types'

const BASE = ''

function getToken(): string | null {
  return localStorage.getItem('ns-lite-token')
}

function setToken(token: string) {
  localStorage.setItem('ns-lite-token', token)
}

function clearToken() {
  localStorage.removeItem('ns-lite-token')
}

function getUsername(): string | null {
  return localStorage.getItem('ns-lite-username')
}

function setUsername(name: string) {
  localStorage.setItem('ns-lite-username', name)
}

async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (opts.body && !(opts.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${BASE}${path}`, { ...opts, headers })

  if (res.status === 401) {
    clearToken()
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const text = await res.text()
    let detail = text
    try {
      const json = JSON.parse(text)
      detail = json.detail || text
    } catch {}
    throw new Error(detail)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function login(username: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams({ username, password })
  const res = await fetch(`${BASE}/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!res.ok) {
    const text = await res.text()
    let detail = text
    try {
      const json = JSON.parse(text)
      detail = json.detail || text
    } catch {}
    throw new Error(detail)
  }
  const data: TokenResponse = await res.json()
  setToken(data.access_token)
  setUsername(data.username)
  return data
}

export function logout() {
  clearToken()
  localStorage.removeItem('ns-lite-username')
}

export function isAuthenticated(): boolean {
  return getToken() !== null
}

export function currentUser(): string | null {
  return getUsername()
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

export function getStats(): Promise<Stats> {
  return apiFetch<Stats>('/api/stats')
}

// ---------------------------------------------------------------------------
// Groups
// ---------------------------------------------------------------------------

export function getGroups(): Promise<Group[]> {
  return apiFetch<Group[]>('/api/groups')
}

export function getGroupsDetail(): Promise<GroupDetail[]> {
  return apiFetch<GroupDetail[]>('/api/groups-detail')
}

export function updateGroup(
  id: string,
  data: { miss_threshold?: number; quarantine_hours?: number; description?: string },
): Promise<GroupDetail> {
  return apiFetch<GroupDetail>(`/api/groups/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteGroup(id: string): Promise<void> {
  return apiFetch<void>(`/api/groups/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// IPs
// ---------------------------------------------------------------------------

export function getIP(ip: string): Promise<IPAddress> {
  return apiFetch<IPAddress>(`/api/ips/${ip}`)
}

export function getAvailable(group?: string, count = 10): Promise<AvailableResponse> {
  const params = new URLSearchParams({ count: String(count) })
  if (group) params.set('group', group)
  return apiFetch<AvailableResponse>(`/api/available?${params}`)
}

export function reserveIP(ip: string, status: string): Promise<{ ip: string; status: string; message: string }> {
  return apiFetch(`/api/ips/${ip}/reserve`, {
    method: 'PUT',
    body: JSON.stringify({ status }),
  })
}

// ---------------------------------------------------------------------------
// Scan
// ---------------------------------------------------------------------------

export function triggerScan(data: { group?: string; ips?: string[] }): Promise<ScanResponse> {
  return apiFetch<ScanResponse>('/api/scan', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ---------------------------------------------------------------------------
// Import
// ---------------------------------------------------------------------------

export function importFile(file: File, group?: string): Promise<ImportResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const params = group ? `?group=${encodeURIComponent(group)}` : ''
  return apiFetch<ImportResponse>(`/api/import${params}`, {
    method: 'POST',
    body: formData,
  })
}

// ---------------------------------------------------------------------------
// WebSocket — real-time scan
// ---------------------------------------------------------------------------

export function connectScanWS(onMessage: (msg: WSMessage) => void): WebSocket {
  const token = getToken()
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${proto}//${location.host}/ws/scan?token=${token}`)

  ws.onmessage = (event) => {
    try {
      const msg: WSMessage = JSON.parse(event.data)
      onMessage(msg)
    } catch {}
  }

  return ws
}
