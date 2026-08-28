# ns-lite

[![CI](https://github.com/Salar-prog/netscan-lite/actions/workflows/ci.yml/badge.svg)](https://github.com/Salar-prog/netscan-lite/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-live-blue.svg)](https://salar-prog.github.io/netscan-lite/)

Lightweight IP discovery with quarantine logic.

Extracted from [NetScan](https://github.com/Salar-prog/netscan) — scans specific IPs from CSV/XLSX files and tracks availability over time. No dashboard, no scheduler, no bloat.

## Features

- **CSV/XLSX import** — load IPs from spreadsheets with group support
- **Targeted scanning** — scan all IPs, a group, or specific addresses
- **Hostname discovery** — captures hostnames via reverse DNS (requires PTR records)
- **Multi-probe detection** — uses ARP, ICMP, and TCP probes to determine host availability
- **Quarantine logic** — safe availability tracking with two-factor release (miss count + time)
- **Groups** — organize IPs with per-group quarantine settings
- **CLI + REST API** — use from terminal or integrate with Terraform/CI pipelines
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

## CLI Commands

```bash
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
| `GET` | `/health` | Health check |
| `GET` | `/api/groups` | List all groups |
| `GET` | `/api/available` | Get available IPs |
| `GET` | `/api/ips/{ip}` | Get IP status |
| `POST` | `/api/scan` | Trigger a scan |

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

# Health check
curl http://localhost:8000/health

# List groups
curl http://localhost:8000/api/groups | jq .

# Get 3 available infra IPs
curl "http://localhost:8000/api/available?group=infra&count=3" | jq .

# Check a specific IP
curl http://localhost:8000/api/ips/10.0.0.1 | jq .

# Trigger a scan for a group
curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{"group": "infra"}' | jq .

# Trigger a scan for specific IPs
curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{"ips": ["10.0.0.1", "10.0.0.5"]}' | jq .
```

### Python

```python
import requests

BASE = "http://localhost:8000"

# Health check
requests.get(f"{BASE}/health").json()
# {'status': 'ok'}

# List groups
groups = requests.get(f"{BASE}/api/groups").json()
for g in groups:
    print(f"{g['name']}: threshold={g['miss_threshold']}, quarantine={g['quarantine_hours']}h")

# Get available IPs
resp = requests.get(f"{BASE}/api/available", params={"group": "infra", "count": 3})
ips = resp.json()["available_ips"]
print(f"Available: {ips}")

# Get IP status
ip_info = requests.get(f"{BASE}/api/ips/10.0.0.1").json()
print(f"Status: {ip_info['status']}, misses: {ip_info['consecutive_misses']}")

# Trigger scan
result = requests.post(f"{BASE}/api/scan", json={"group": "infra"}).json()
print(f"Scanned {result['scanned']}: {result['active']} active, {result['uncertain']} uncertain")
```

### JavaScript / Node.js

```javascript
const BASE = "http://localhost:8000";

// Get available IPs
const resp = await fetch(`${BASE}/api/available?group=infra&count=3`);
const { available_ips } = await resp.json();
console.log("Available:", available_ips);

// Trigger scan
const result = await fetch(`${BASE}/api/scan`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ group: "infra" }),
}).then(r => r.json());
console.log(`Scanned ${result.scanned}: ${result.active} active`);
```

### PowerShell

```powershell
$base = "http://localhost:8000"

# Get available IPs
$ips = Invoke-RestMethod "$base/api/available?group=infra&count=3"
$ips.available_ips

# Trigger scan
$body = @{ group = "infra" } | ConvertTo-Json
Invoke-RestMethod -Uri "$base/api/scan" -Method POST -Body $body -ContentType "application/json"
```

---

## Terraform Integration

```hcl
# Get available IPs from ns-lite
data "http" "available_ips" {
  url = "http://ns-lite:8000/api/available?group=infra&count=3"
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
- name: Get available IPs from ns-lite
  ansible.builtin.uri:
    url: "http://ns-lite:8000/api/available?group=database&count=2"
    return_content: yes
  register: ns_lite

- name: Print available IPs
  ansible.builtin.debug:
    msg: "Available IPs: {{ ns_lite.content | from_json | json_query('available_ips') }}"
```

---

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

## How Quarantine Works

1. **First scan**: IP responds → `ACTIVE_DETECTED`
2. **IP stops responding**: Status changes to `UNCERTAIN_FIREWALLED`
3. **Subsequent scans**: If IP keeps missing, `consecutive_misses` increments
4. **Quarantine complete**: After `miss_threshold` misses AND `quarantine_hours` elapsed → `AVAILABLE_CANDIDATE`

This two-factor approach prevents freeing an IP just because a firewall dropped a ping.

## Scanner Behavior

The scanner uses nmap with multiple probe types depending on privilege level:

| Privilege | Probes Used |
|-----------|-------------|
| **Root / CAP_NET_RAW** | ARP ping (`-PR`), ICMP echo (`-PE`), ICMP timestamp (`-PP`), TCP SYN ping (`-PS`), SYN scan (`-sS`) |
| **Unprivileged** | ICMP echo (`-PE`), TCP ACK ping (`-PA`), TCP connect scan (`-sT`) |

Hostnames are captured via reverse DNS (`-R` flag) and require PTR records on the target IPs. The `discovery_method` field records which probe succeeded: `ARP`, `ICMP`, `TCP_SYN`, or `TCP_CONNECT`.

## License

MIT
