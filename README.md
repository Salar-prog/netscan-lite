# ns-lite

[![CI](https://github.com/Salar-prog/netscan-lite/actions/workflows/ci.yml/badge.svg)](https://github.com/Salar-prog/netscan-lite/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-live-blue.svg)](https://salar-prog.github.io/netscan-lite/)

> **Note:** ns-lite v1 is intended for **internal use** as an API-first IP discovery tool. It is not hardened for public-facing deployments. See [Known Limitations](#known-limitations) for details.

Lightweight IP discovery with quarantine logic.

Extracted from [NetScan](https://github.com/Salar-prog/netscan) — scans specific IPs from CSV/XLSX files and tracks availability over time. Includes a React dashboard for visual monitoring.

## Features

- **CSV/XLSX import** — load IPs from spreadsheets with group support
- **Targeted scanning** — scan all IPs, a group, or specific addresses
- **Hostname discovery** — captures hostnames via reverse DNS (requires PTR records)
- **Multi-probe detection** — uses ARP, ICMP, and TCP probes to determine host availability
- **Quarantine logic** — safe availability tracking with two-factor release (miss count + time)
- **Groups** — organize IPs with per-group quarantine settings
- **Web dashboard** — real-time IP monitoring, scan triggers, CSV import, group management
- **CLI + REST API** — use from terminal or integrate with Terraform/CI pipelines
- **LDAP authentication** — JWT-based API auth backed by LDAP; dev mode skips LDAP entirely
- **JSON output** — every command supports `--json-output` for automation

## Quick Start

```bash
pip install -e ".[xlsx]"

# Import IPs
ns-lite import --file ips.csv

# Scan them
ns-lite scan

# Get available IPs
ns-lite available --count 3
```

### Dashboard

Start the server and open the dashboard in your browser:

```bash
ns-lite serve
# Open http://localhost:8000 in your browser
```

See [Dashboard Guide](https://salar-prog.github.io/netscan-lite/dashboard/) for details.

## CLI Commands

```bash
ns-lite auth --username jsmith              # login, store JWT token
ns-lite import --file ips.csv              # import from CSV
ns-lite import --file ips.xlsx --group db  # import with group override
ns-lite scan --group infra                 # scan a group
ns-lite scan --ip 10.0.0.1,10.0.0.5       # scan specific IPs
ns-lite scan --no-ports                    # host discovery only (no port scan)
ns-lite available --group infra --count 3  # get available IPs
ns-lite available --json-output            # JSON for Terraform
ns-lite groups                             # list groups
ns-lite groups --json-output               # JSON output
ns-lite status 10.0.0.1                    # check IP status
ns-lite status 10.0.0.1 --json-output     # JSON output
ns-lite serve                              # start API server
ns-lite serve --host 0.0.0.0 --port 9000  # custom bind
```

## CSV/XLSX Format

```csv
ip,hostname,group
10.0.0.1,gateway-01,infra
10.0.0.5,db-primary,database
10.0.0.12,,general
```

| Column | Required | Description |
|--------|----------|-------------|
| `ip` | yes | IPv4 address |
| `hostname` | no | Friendly name or reverse DNS hostname |
| `group` | no | Group name (default: `"default"`) |

---

## API Reference

ns-lite exposes a REST API via FastAPI. Start the server:

```bash
ns-lite serve                          # http://localhost:8000
ns-lite serve --host 0.0.0.0 --port 9000  # custom bind
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/token` | Login and get JWT token |
| `GET` | `/health` | Health check (no auth required) |
| `GET` | `/api/stats` | Dashboard overview stats |
| `GET` | `/api/groups` | List all groups |
| `GET` | `/api/groups-detail` | List groups with IP counts |
| `PUT` | `/api/groups/{id}` | Update group quarantine settings |
| `DELETE` | `/api/groups/{id}` | Delete group and its IPs |
| `GET` | `/api/available` | Get available IPs |
| `GET` | `/api/ips` | List IPs (paginated, filterable) |
| `GET` | `/api/ips/{ip}` | Get IP status |
| `POST` | `/api/ips/{ip}/scan` | Scan a single IP |
| `PUT` | `/api/ips/{ip}/reserve` | Reserve or release an IP |
| `POST` | `/api/scan` | Trigger a scan |
| `POST` | `/api/import` | Import IPs from CSV/XLSX |
| `WS` | `/ws/scan` | Real-time scan progress |

---

### Health Check

```
GET /health
```

```json
{"status": "ok"}
```

Use this for load balancer health checks or monitoring uptime.

---

### List Groups

```
GET /api/groups
```

```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "infra",
    "miss_threshold": 3,
    "quarantine_hours": 48
  },
  {
    "id": "e5f6g7h8-...",
    "name": "database",
    "miss_threshold": 5,
    "quarantine_hours": 72
  }
]
```

Each group has its own quarantine settings. Use this to discover what groups exist before querying available IPs.

---

### Get Available IPs

Returns IPs that have been quarantined long enough and are safe to provision.

```
GET /api/available?group=infra&count=3
```

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `group` | string | all groups | Filter by group name |
| `count` | int | 1 | Number of IPs to return (max: 100) |

```json
{
  "available_ips": ["10.0.0.20", "10.0.0.25", "10.0.0.12"],
  "count": 3
}
```

**Example — get 5 available database IPs:**

```bash
curl "http://localhost:8000/api/available?group=database&count=5"
```

**Example — get any available IP:**

```bash
curl "http://localhost:8000/api/available?count=1"
```

**Error — group not found:**

```json
{
  "detail": "Group 'nonexistent' not found"
}
```

---

### Get IP Status

Returns full status details for a single IP address.

```
GET /api/ips/{ip}
```

```json
{
  "ip": "10.0.0.1",
  "status": "ACTIVE_DETECTED",
  "hostname": "gateway-01",
  "mac_address": "aa:bb:cc:dd:ee:ff",
  "mac_vendor": "Cisco Systems",
  "consecutive_misses": 0,
  "first_seen_at": "2026-08-28T10:00:00",
  "last_seen_at": "2026-08-28T12:00:00",
  "last_scanned_at": "2026-08-28T12:00:00"
}
```

**Status values:**

| Status | Meaning |
|--------|---------|
| `ACTIVE_DETECTED` | IP responded to the last scan |
| `AVAILABLE_CANDIDATE` | Quarantine complete — safe to provision |
| `UNCERTAIN_FIREWALLED` | IP missed recent scans, in quarantine |
| `ASSIGNED_RESERVED` | IP is reserved and locked |

**Example — check a specific IP:**

```bash
curl http://localhost:8000/api/ips/10.0.0.1
```

**Error — IP not found:**

```json
{
  "detail": "IP '10.0.0.99' not found"
}
```

---

### Trigger Scan

Runs nmap against the specified IPs and updates their status in the database.

```
POST /api/scan
Content-Type: application/json
```

**Scan all IPs in a group:**

```json
{"group": "infra"}
```

**Scan specific IPs:**

```json
{"ips": ["10.0.0.1", "10.0.0.5", "10.0.0.12"]}
```

**Scan all IPs (no filter):**

```json
{}
```

**Response:**

```json
{
  "message": "Scanned 5 IP(s)",
  "scanned": 5,
  "active": 3,
  "uncertain": 1,
  "available": 1
}
```

**Error — no IPs to scan:**

```json
{
  "detail": "No IPs to scan"
}
```

**Error — scan timeout/failure:**

```json
{
  "detail": "Scan failed: Nmap scan timed out after 300 seconds for 50 targets"
}
```

**Validation — invalid IP address:**

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "ips", 0],
      "msg": "Value error, Invalid IPv4 address: not-an-ip"
    }
  ]
}
```

**Example — trigger scan via curl:**

```bash
curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{"group": "infra"}'
```

```bash
curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{"ips": ["10.0.0.1", "10.0.0.5"]}'
```

---

## API Usage Examples

### cURL

```bash
# Start the server
ns-lite serve &

# Get a token (skip in dev mode when LDAP_ENABLED=false)
TOKEN=$(curl -s -X POST http://localhost:8000/token \
  -d "username=jsmith&password=secret123" | jq -r '.access_token')

# Health check
curl http://localhost:8000/health

# List groups
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/groups | jq .

# Get 3 available infra IPs
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/available?group=infra&count=3" | jq .

# Check a specific IP
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/ips/10.0.0.1 | jq .

# Trigger a scan for a group
curl -X POST http://localhost:8000/api/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"group": "infra"}' | jq .

# Trigger a scan for specific IPs
curl -X POST http://localhost:8000/api/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ips": ["10.0.0.1", "10.0.0.5"]}' | jq .
```

### Python

```python
import requests

BASE = "http://localhost:8000"

# Get a token (skip in dev mode when LDAP_ENABLED=false)
resp = requests.post(f"{BASE}/token", data={"username": "jsmith", "password": "secret123"})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Health check
requests.get(f"{BASE}/health").json()
# {'status': 'ok'}

# List groups
groups = requests.get(f"{BASE}/api/groups", headers=headers).json()
for g in groups:
    print(f"{g['name']}: threshold={g['miss_threshold']}, quarantine={g['quarantine_hours']}h")

# Get available IPs
resp = requests.get(f"{BASE}/api/available", params={"group": "infra", "count": 3}, headers=headers)
ips = resp.json()["available_ips"]
print(f"Available: {ips}")

# Get IP status
ip_info = requests.get(f"{BASE}/api/ips/10.0.0.1", headers=headers).json()
print(f"Status: {ip_info['status']}, misses: {ip_info['consecutive_misses']}")

# Trigger scan
result = requests.post(f"{BASE}/api/scan", json={"group": "infra"}, headers=headers).json()
print(f"Scanned {result['scanned']}: {result['active']} active, {result['uncertain']} uncertain")
```

### JavaScript / Node.js

```javascript
const BASE = "http://localhost:8000";

// Get a token (skip in dev mode when LDAP_ENABLED=false)
const tokenResp = await fetch(`${BASE}/token`, {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body: "username=jsmith&password=secret123",
});
const { access_token } = await tokenResp.json();
const headers = { Authorization: `Bearer ${access_token}` };

// Get available IPs
const resp = await fetch(`${BASE}/api/available?group=infra&count=3`, { headers });
const { available_ips } = await resp.json();
console.log("Available:", available_ips);

// Trigger scan
const result = await fetch(`${BASE}/api/scan`, {
  method: "POST",
  headers: { ...headers, "Content-Type": "application/json" },
  body: JSON.stringify({ group: "infra" }),
}).then(r => r.json());
console.log(`Scanned ${result.scanned}: ${result.active} active`);
```

### PowerShell

```powershell
$base = "http://localhost:8000"

# Get a token (skip in dev mode when LDAP_ENABLED=false)
$tokenResp = Invoke-RestMethod "$base/token" -Method POST -Body "username=jsmith&password=secret123" -ContentType "application/x-www-form-urlencoded"
$headers = @{ Authorization = "Bearer $($tokenResp.access_token)" }

# Get available IPs
$ips = Invoke-RestMethod "$base/api/available?group=infra&count=3" -Headers $headers
$ips.available_ips

# Trigger scan
$body = @{ group = "infra" } | ConvertTo-Json
Invoke-RestMethod -Uri "$base/api/scan" -Method POST -Body $body -ContentType "application/json" -Headers $headers
```

---

## Terraform Integration

```hcl
# Get a token
data "http" "token" {
  url             = "http://ns-lite:8000/token"
  method          = "POST"
  request_headers = { "Content-Type" = "application/x-www-form-urlencoded" }
  request_body    = "username=${var.ns_lite_user}&password=${var.ns_lite_pass}"
}

# Get available IPs
data "http" "available_ips" {
  url = "http://ns-lite:8000/api/available?group=infra&count=3"
  request_headers = {
    "Authorization" = "Bearer ${jsondecode(data.http.token.body).access_token}"
  }
}

locals {
  ips = jsondecode(data.http.available_ips.body).available_ips
}

resource "aws_instance" "nodes" {
  count         = length(local.ips)
  ami           = "ami-..."
  instance_type = "t3.micro"
  private_ip    = local.ips[count.index]

  tags = {
    Name = "node-${count.index}"
    IP   = local.ips[count.index]
  }
}
```

### Ansible

```yaml
- name: Get token from ns-lite
  ansible.builtin.uri:
    url: "http://ns-lite:8000/token"
    method: POST
    body_format: form-urlencoded
    body:
      username: "{{ ns_lite_user }}"
      password: "{{ ns_lite_pass }}"
    status_code: 200
  register: token_resp

- name: Get available IPs from ns-lite
  ansible.builtin.uri:
    url: "http://ns-lite:8000/api/available?group=database&count=2"
    headers:
      Authorization: "Bearer {{ token_resp.json.access_token }}"
    return_content: yes
  register: ns_lite

- name: Print available IPs
  ansible.builtin.debug:
    msg: "Available IPs: {{ ns_lite.content | from_json | json_query('available_ips') }}"
```

---

## Production Deployment

ns-lite supports Docker and bare metal deployment with PostgreSQL for production use.

### Docker Compose (Recommended)

```bash
# Clone and configure
git clone https://github.com/Salar-prog/netscan-lite.git
cd netscan-lite
cp .env.example .env
# Edit .env with your settings

# Start with PostgreSQL
docker compose up -d
```

### Bare Metal

```bash
pip install -e ".[xlsx,postgres]"

# Start with multiple workers
ns-lite serve --host 0.0.0.0 --port 8000 --workers 4
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `LDAP_ENABLED` | Yes | Set to `true` for production |
| `JWT_SECRET_KEY` | Recommended | Token signing key |
| `WORKERS` | No | Gunicorn workers (default: 1) |

For full deployment options, see the [Deployment Guide](https://salar-prog.github.io/netscan-lite/deployment/).

## Configuration

Environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./ns-lite.db` | Database URL |
| `DEBUG` | `false` | Debug logging |
| `DEFAULT_MISS_THRESHOLD` | `3` | Misses before uncertain |
| `DEFAULT_QUARANTINE_HOURS` | `48` | Hours before available |
| `NMAP_TIMEOUT_SECONDS` | `300` | Per-scan timeout |
| `NMAP_TIMING_TEMPLATE` | `-T4` | Nmap timing template |
| `TOP_TCP_PORTS` | `80,443,22,445,3389,8080,8443,53` | Ports to scan |

### LDAP Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `LDAP_ENABLED` | `false` | Enable LDAP auth |
| `DEV_AUTH_ENABLED` | `false` | Allow dev-mode auth when `LDAP_ENABLED=false` |
| `LDAP_SERVER` | `ldap://localhost` | LDAP server URL |
| `LDAP_BIND_DN` | `cn=admin,dc=example,dc=com` | Service account DN |
| `LDAP_BIND_PASSWORD` | (empty) | Service account password |
| `LDAP_SEARCH_BASE` | `dc=example,dc=com` | Base DN for user search |
| `LDAP_SEARCH_FILTER` | `(sAMAccountName={username})` | Search filter |
| `LDAP_USE_SSL` | `false` | Use LDAPS (implicit TLS on port 636) |

### JWT Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | (auto-generated) | Token signing key |
| `JWT_EXPIRY_HOURS` | `24` | Token lifetime |

## How Quarantine Works

1. **First scan**: IP responds → `ACTIVE_DETECTED`
2. **IP stops responding**: Status changes to `UNCERTAIN_FIREWALLED`
3. **Subsequent scans**: If IP keeps missing, `consecutive_misses` increments
4. **Quarantine complete**: After `miss_threshold` misses AND `quarantine_hours` elapsed → `AVAILABLE_CANDIDATE`

This two-factor approach prevents freeing an IP just because a firewall dropped a ping.

## Known Limitations

ns-lite v1 is designed for **internal use** as an API-first tool. The following limitations are known and will be addressed in future releases:

### Synchronous Scan Endpoint

`POST /api/scan` is synchronous — it blocks the HTTP worker for the entire nmap scan duration (up to 300s default). This is acceptable for single-team internal use but will not scale for multi-user or public-facing deployments. Background job support and async scan processing are planned for a future release.

### Multi-User Concurrency

The rate limiter uses in-memory per-worker state. With `WORKERS > 1`, the effective rate limit is `120 × workers`. A Redis-backed rate limiter is planned for future releases to support proper multi-user deployments.

### JWT Token Storage (Dashboard)

The React dashboard stores JWT tokens in `localStorage`. This is acceptable for an internal tool behind TLS but would be a security risk for public-facing deployments. httpOnly cookie-based auth is planned for a future release.

### CLI Event Loop

`ns-lite scan` uses `asyncio.run()` which will fail if called from within an already-running event loop (e.g., from another async context). The CLI is a tertiary interface; the API should be used for programmatic access.

### WebSocket Auth

WebSocket connections pass the JWT token as a query parameter (`?token=...`), which may appear in server and proxy logs. This is standard for WebSocket auth but worth noting for security auditing.

## Scanner Behavior

The scanner uses nmap with multiple probe types depending on privilege level:

| Privilege | Probes Used |
|-----------|-------------|
| **Root / CAP_NET_RAW** | ARP ping (`-PR`), ICMP echo (`-PE`), ICMP timestamp (`-PP`), TCP SYN ping (`-PS`), SYN scan (`-sS`) |
| **Unprivileged** | ICMP echo (`-PE`), TCP ACK ping (`-PA`), TCP connect scan (`-sT`) |

Hostnames are captured via reverse DNS (`-R` flag) and require PTR records on the target IPs. The `discovery_method` field records which probe succeeded: `ARP`, `ICMP`, `TCP_SYN`, or `TCP_CONNECT`.

## License

MIT
