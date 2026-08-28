export type IPStatus =
  | 'ACTIVE_DETECTED'
  | 'AVAILABLE_CANDIDATE'
  | 'UNCERTAIN_FIREWALLED'
  | 'ASSIGNED_RESERVED'

export interface Stats {
  total_ips: number
  active: number
  uncertain: number
  available: number
  reserved: number
  groups: number
  last_scan: string | null
}

export interface Group {
  id: string
  name: string
  miss_threshold: number
  quarantine_hours: number
}

export interface GroupDetail extends Group {
  description: string | null
  ip_count: number
}

export interface IPAddress {
  ip: string
  status: IPStatus
  hostname: string | null
  mac_address: string | null
  mac_vendor: string | null
  open_ports: { port: number; protocol: string; state: string; service: string }[]
  discovery_method: string | null
  consecutive_misses: number
  first_seen_at: string | null
  last_seen_at: string | null
  last_scanned_at: string | null
}

export interface AvailableResponse {
  available_ips: string[]
  count: number
}

export interface ScanResponse {
  message: string
  scanned: number
  active: number
  uncertain: number
  available: number
}

export interface ImportResponse {
  imported: number
  skipped: number
  errors: string[]
}

export interface TokenResponse {
  access_token: string
  token_type: string
  username: string
}

export interface WSProgress {
  type: 'progress'
  ip: string
  status: 'scanning' | 'done'
  result?: IPStatus
}

export interface WSComplete {
  type: 'complete'
  scanned: number
  active: number
  uncertain: number
  available: number
}

export interface WSError {
  type: 'error'
  detail: string
}

export type WSMessage = WSProgress | WSComplete | WSError
