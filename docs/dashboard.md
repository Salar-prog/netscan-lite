# Dashboard

ns-lite includes a self-hosted React dashboard for visual IP monitoring, scan management, and group administration.

## Getting Started

Start the server and open your browser:

```bash
ns-lite serve
# Open http://localhost:8000
```

!!! note

    The dashboard requires a valid JWT token. In dev mode (`LDAP_ENABLED=false` and `DEV_AUTH_ENABLED=true`), any username/password combination is accepted.

## Features

### Overview

The home page shows a summary of your IP inventory:

- **Total IPs** — all tracked IP addresses
- **Active** — IPs that responded to the last scan
- **Uncertain** — IPs in quarantine (missed recent scans)
- **Available** — IPs that passed quarantine and are safe to provision
- **Reserved** — IPs locked for specific use
- **Groups** — number of configured groups
- **Last Scan** — timestamp of the most recent scan

### IP List

Browse all tracked IPs with filtering, searching, and pagination:

- Filter by **group** or **status**
- Search by **IP address** or **hostname**
- Click any row to view full details

### IP Detail

View complete status for a single IP:

- Status, hostname, MAC address and vendor
- Open ports from last scan
- Discovery method (ARP, ICMP, TCP_SYN, TCP_CONNECT)
- Consecutive misses count
- First seen, last seen, last scanned timestamps
- **Scan** — trigger an immediate scan of this IP
- **Reserve/Release** — lock or unlock the IP

### Group Manager

View and edit quarantine settings per group:

- **Miss threshold** — consecutive misses before uncertain
- **Quarantine hours** — time in UNCERTAIN before AVAILABLE
- **Description** — optional group description
- **Delete** — remove a group and all its IPs

### Scan Trigger

Run scans from the dashboard with live progress:

- Scan **by group** or **specific IPs**
- Real-time WebSocket progress bar
- Live results feed showing each IP's status as it completes
- Cancel in-progress scans
- Completion summary with elapsed time

### Import

Import IPs via CSV or XLSX with drag & drop:

- Drag a file onto the drop zone, or click to browse
- **CSV preview** — first 10 rows shown with per-row validation
- Group override option
- Results: imported, skipped, errors

## Architecture

```
dashboard/
  src/
    api.ts          # Fetch wrapper, WebSocket client, auth helpers
    types.ts        # TypeScript interfaces
    App.tsx         # Router with protected routes
    components/
      Login.tsx     # Login page
      Layout.tsx    # Sidebar navigation
      Dashboard.tsx # Stats overview
      IpList.tsx    # Filterable IP table
      IpDetail.tsx  # IP detail with actions
      GroupManager.tsx  # Group settings
      ScanTrigger.tsx   # Scan with live progress
      Import.tsx    # CSV/XLSX import
```

## Development

To modify the dashboard source:

```bash
cd netscan_lite/dashboard
npm install
npm run dev    # Vite dev server with hot reload (proxies to :8000)
npm run build  # Build to ../static/ for production
```

The dev server proxies API requests to `localhost:8000`, so run `ns-lite serve` in a separate terminal.

## Authentication Flow

1. User navigates to `/login`
2. Enters username and password
3. Frontend sends `POST /token` with form data
4. Backend returns JWT token
5. Token stored in `localStorage`
6. All API requests include `Authorization: Bearer <token>` header
7. On 401 response, user is redirected to `/login`

## WebSocket Protocol

The scan trigger uses a WebSocket for real-time progress:

1. Frontend connects to `ws://host/ws/scan?token=<jwt>`
2. Sends target: `{"group": "infra"}` or `{"ips": ["10.0.0.1"]}`
3. Server streams progress: `{"type": "progress", "ip": "...", "status": "scanning|done", "result": "..."}`
4. On completion: `{"type": "complete", "scanned": N, "active": N, ...}`
5. On error: `{"type": "error", "detail": "..."}`

## Tech Stack

- **React 19** with TypeScript
- **Vite** for bundling (output to `netscan_lite/static/`)
- **Tailwind CSS v4** for styling
- **react-router-dom** for client-side routing
- Served by FastAPI `StaticFiles` mount at `/`
