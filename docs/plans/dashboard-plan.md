# Dashboard Implementation Plan — ns-lite Self-Hosted GUI

## Overview

Add a React SPA dashboard bundled into the FastAPI app. Single `ns-lite serve` serves both API + dashboard. WebSocket for real-time scan updates.

**Stack:** React 18 + Vite + Tailwind CSS + react-router-dom  
**Backend mount:** FastAPI `StaticFiles` serving from `netscan_lite/static/`  
**Real-time:** WebSocket at `/ws/scan`  
**Auth:** JWT stored in localStorage, sent in `Authorization` header  
**Layout:** Sidebar navigation  
**Colors:** Teal primary, amber accent (matching existing MkDocs site)

---

## Phase 1: Backend Foundation

### Scope
- `netscan_lite/api.py` — new endpoints
- `netscan_lite/scanner/service.py` — progress callback
- `netscan_lite/main.py` — static files mount + WebSocket

### New Endpoints

#### GET `/api/v1/stats`

Dashboard overview. No params.

```json
{
  "total_ips": 120,
  "active": 85,
  "uncertain": 15,
  "available": 18,
  "reserved": 2,
  "groups": 4,
  "last_scan": "2026-08-28T12:00:00Z"
}
```

#### POST `/api/v1/import`

Multipart file upload.

- `file`: CSV or XLSX (required)
- `group`: string (optional override)

```json
{"imported": 5, "skipped": 2, "errors": ["Row 3: invalid IP 'x.x.x.x'"]}
```

#### PUT `/api/v1/groups/{group_id}`

Update group quarantine settings.

```json
// Request
{"miss_threshold": 5, "quarantine_hours": 72}
// Response
{"id": "...", "name": "infra", "miss_threshold": 5, "quarantine_hours": 72}
```

#### DELETE `/api/v1/groups/{group_id}`

Delete group and all its IPs. Returns `204`.

#### PUT `/api/v1/ips/{ip_address}/reserve`

Reserve or release an IP.

```json
// Request
{"status": "ASSIGNED_RESERVED"}
// or
{"status": "AVAILABLE_CANDIDATE"}
```

#### WebSocket `/ws/scan`

Query param: `?token=<jwt>`

Client sends JSON:
```json
{"group": "infra"} or {"ips": ["10.0.0.1", "10.0.0.5"]}
```

Server pushes:
```json
{"type": "progress", "ip": "10.0.0.1", "status": "scanning"}
{"type": "progress", "ip": "10.0.0.1", "status": "done", "result": "ACTIVE_DETECTED"}
{"type": "complete", "scanned": 5, "active": 3, "uncertain": 1, "available": 1}
{"type": "error", "detail": "No IPs to scan"}
```

### Scanner Service Change

Add optional `on_progress` callback to `scan_ips()`:

```python
async def scan_ips(ips, session, group=None, scan_ports=True, on_progress=None):
    # ... existing logic ...
    for ip_str in ips:
        if on_progress:
            await on_progress({"type": "progress", "ip": ip_str, "status": "scanning"})
        # ... scan and classify ...
        if on_progress:
            await on_progress({"type": "progress", "ip": ip_str, "status": "done", "result": outcome.new_status.value})
```

### Static Files Mount

In `main.py`, after routers:

```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="dashboard")
```

The `html=True` flag serves `index.html` for SPA routes (React Router handles client-side routing).

### Files Modified
- `netscan_lite/api.py` — 6 new endpoints
- `netscan_lite/scanner/service.py` — add `on_progress` callback
- `netscan_lite/main.py` — mount static files

---

## Phase 2: React Scaffold

### Scope
- `netscan_lite/dashboard/` — new directory (React source)
- `netscan_lite/static/` — gitignored build output

### Project Setup

```bash
cd netscan_lite/dashboard
npm create vite@latest . -- --template react-ts
npm install react-router-dom
npm install -D tailwindcss @tailwindcss/vite
```

### Files

```
netscan_lite/dashboard/
  index.html
  package.json
  vite.config.ts
  tailwind.config.js
  tsconfig.json
  src/
    main.tsx
    App.tsx
    api.ts              ← fetch wrapper + WebSocket client
    types.ts            ← TypeScript interfaces matching API models
    components/
      Login.tsx
      Layout.tsx        ← sidebar + header + outlet
      Dashboard.tsx     ← overview stats
      IpList.tsx        ← filterable table
      IpDetail.tsx      ← single IP view
      GroupManager.tsx  ← list + edit modal
      ScanTrigger.tsx   ← scan form + WebSocket progress
      Import.tsx        ← file upload + preview
```

### Vite Config

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../static',   // output to netscan_lite/static/
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/token': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    }
  }
})
```

### API Client (`api.ts`)

```typescript
const BASE = ""  // same origin in prod, proxy in dev

function getToken(): string | null { return localStorage.getItem("token") }

async function apiFetch(path: string, opts: RequestInit = {}) {
  const token = getToken()
  const headers = { ...opts.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) }
  const res = await fetch(`${BASE}${path}`, { ...opts, headers })
  if (res.status === 401) { localStorage.removeItem("token"); window.location.href = "/login" }
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

function wsConnect(path: string): WebSocket {
  const token = getToken()
  return new WebSocket(`${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}${path}?token=${token}`)
}
```

### Routing

```
/login          → Login
/               → Layout (protected)
  /             → Dashboard
  /ips          → IpList
  /ips/:ip      → IpDetail
  /groups       → GroupManager
  /scan         → ScanTrigger
  /import       → Import
```

Protected route: redirect to `/login` if no JWT in localStorage.

---

## Phase 3: Core Screens

### Login (`Login.tsx`)

- Centered card with logo + title
- Username and password inputs
- "Sign In" button → POST `/token` → store token → redirect to `/`
- Error message display
- Tailwind: teal background, white card

### Layout (`Layout.tsx`)

- Fixed sidebar (w-64, teal-800 background, white text)
  - Logo + "ns-lite" title
  - Nav links with icons: Dashboard, IPs, Groups, Scan, Import
  - Active link highlight (teal-600)
  - User info + logout button at bottom
- Main content area (right of sidebar)
- Header bar with page title

### Dashboard (`Dashboard.tsx`)

- 5 stat cards in a grid:
  - Total IPs (blue)
  - Active (green)
  - Uncertain (yellow)
  - Available (teal)
  - Reserved (red)
- Groups table: name, IP count, miss_threshold, quarantine_hours
- Last scan timestamp
- Quick action buttons: "Scan All", "Import IPs"

### IpList (`IpList.tsx`)

- Top bar: group filter dropdown, status filter dropdown, search input
- Table columns: IP, Hostname, Status (color badge), Group, MAC, Vendor, Misses, Last Seen
- Sortable column headers (click to sort)
- Row click → navigate to `/ips/:ip`
- Pagination (or infinite scroll — pagination is simpler)
- Empty state when no IPs

### IpDetail (`IpDetail.tsx`)

- Back button → `/ips`
- IP info card:
  - IP address (large)
  - Status badge (colored)
  - Hostname, MAC, Vendor
  - Group name
  - Discovery method
  - Consecutive misses
- Timestamps: first seen, last seen, last scanned
- Open ports table (port, protocol, state, service)
- Action buttons: "Scan This IP", "Reserve", "Release"

### GroupManager (`GroupManager.tsx`)

- Table: name, description, miss_threshold, quarantine_hours, IP count
- "Create Group" button → modal with form
- Row actions: Edit (modal), Delete (confirmation dialog)
- Edit modal: name, description, miss_threshold (number input), quarantine_hours (number input)
- Delete confirmation: "Delete group and all X IPs in it?"

---

## Phase 4: Interactive Features

### ScanTrigger (`ScanTrigger.tsx`)

- Target selection:
  - Radio: "Group" or "Specific IPs"
  - If Group: dropdown of groups
  - If IPs: textarea (comma-separated)
- "Start Scan" button
- On click: open WebSocket, send scan request
- Progress display:
  - Progress bar (scanned / total)
  - Live feed: each IP with scanning → done status
  - Color-coded results (green=active, yellow=uncertain, teal=available)
- Completion summary card
- "Scan Again" button to reset

### Import (`Import.tsx`)

- Drag & drop zone (or click to browse)
- Accepted: .csv, .xlsx
- Optional group override dropdown
- After file selected:
  - Preview table (first 10 rows)
  - "Import" button
- After import:
  - Results card: imported count, skipped count, error list
  - "Import Another" button

---

## Phase 5: Polish & Docs

- Loading spinners for all async operations
- Error toast/notification component
- Empty states for all lists
- Responsive: sidebar collapses on mobile
- Update README.md with dashboard screenshots/description
- Update docs/cli.md, docs/api.md with dashboard mention
- Build script: `npm run build` in dashboard/ produces static/

---

## Non-Goals

- Multi-user management (single shared JWT)
- Audit log UI
- Dark mode (can add later)
- Mobile-specific layout
- Export/download features
- Real-time IP status polling on dashboard (WebSocket only for scans)

---

## Implementation Order

1. Phase 1 (backend) → commit → test
2. Phase 2 (scaffold) → commit → verify dev server works
3. Phase 3 (core screens) → commit → verify all screens render
4. Phase 4 (interactive) → commit → test scan + import flows
5. Phase 5 (polish) → commit → deploy

Each phase is independently testable and deployable.
