# Quick Start

Get up and running in 3 steps.

## 1. Create Your IP List

Create a CSV file with your IPs:

```csv
ip,hostname,group
10.0.0.1,gateway-01,infra
10.0.0.5,db-primary,database
10.0.0.12,app-01,apps
10.0.0.20,,infra
10.0.0.25,monitoring,infra
```

| Column | Required | Description |
|--------|----------|-------------|
| `ip` | yes | IPv4 address |
| `hostname` | no | Friendly name or reverse DNS hostname |
| `group` | no | Group name (defaults to `"default"`) |

## 2. Import and Scan

```bash
# Import IPs from CSV
ns-lite import --file ips.csv

# Scan all imported IPs
ns-lite scan
```

Output:

```
Scanning 12 IP(s)...

Results: 8 active, 3 uncertain, 1 available
```

## 3. Get Available IPs

```bash
# Get 3 available IPs from the infra group
ns-lite available --group infra --count 3
```

Output:

```
Available IPs (infra):
  10.0.0.20
  10.0.0.25
  10.0.0.12
```

## What Just Happened?

1. **Import** — IPs were added to the database, organized by group
2. **Scan** — nmap probed each IP using ARP/ICMP/TCP depending on your privileges
3. **Classify** — each IP was classified as active, uncertain, or available

The first scan establishes a baseline. Run `ns-lite scan` again later to update the status of each IP.

## Using the API

Start the API server and query it programmatically:

```bash
# Start the server
ns-lite serve &

# Get a token (optional in dev mode, required with LDAP_ENABLED=true)
TOKEN=$(curl -s -X POST http://localhost:8000/token \
  -d "username=jsmith&password=secret123" | jq -r '.access_token')

# Get available IPs via API
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/available?group=infra&count=3" | jq .

# Trigger a scan via API
curl -X POST http://localhost:8000/api/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"group": "infra"}' | jq .
```

## Using the Dashboard

ns-lite includes a React dashboard for visual monitoring. Start the server and open your browser:

```bash
ns-lite serve
# Open http://localhost:8000 in your browser
```

The dashboard provides:

- **Overview** — status counts, group summary, last scan time
- **IP List** — filterable, searchable table with pagination
- **IP Detail** — full status, scan action, reserve/release
- **Groups** — edit quarantine settings per group
- **Scan** — trigger scans with live WebSocket progress
- **Import** — drag & drop CSV/XLSX with preview and validation

## Next Steps

- [CLI Reference](cli.md) — all available commands and flags
- [API Reference](api.md) — REST API with client examples (Python, JS, PowerShell, Terraform)
- [Configuration](config.md) — customize quarantine thresholds, nmap settings, database
