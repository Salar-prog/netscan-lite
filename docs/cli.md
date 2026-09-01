# CLI Reference

All commands are available as `ns-lite <command>`.

## auth

Authenticate and store a JWT token for API access.

```bash
ns-lite auth --username jsmith
ns-lite auth -u jsmith -p secret123
ns-lite auth -u jsmith -p secret123 --server http://remote-host:8000
```

| Flag | Description |
|------|-------------|
| `--username`, `-u` | LDAP username (prompted if not provided) |
| `--password`, `-p` | LDAP password (hidden input, prompted if not provided) |
| `--server`, `-s` | API server URL (default: `http://127.0.0.1:8000`, or `API_BASE_URL` env var) |

The token is saved to `~/.ns-lite/token` and used automatically by other ns-lite commands when `LDAP_ENABLED=true`.

## import

Import IPs from a CSV or XLSX file.

```bash
ns-lite import --file ips.csv
ns-lite import --file ips.xlsx --group database
```

| Flag | Description |
|------|-------------|
| `--file` | Path to CSV or XLSX file (required) |
| `--group` | Override group for all imported IPs |

**CSV/XLSX format:**

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

## scan

Scan IPs using nmap.

```bash
ns-lite scan                        # scan all IPs
ns-lite scan --group infra          # scan a specific group
ns-lite scan --ip 10.0.0.1,10.0.0.5 # scan specific IPs
ns-lite scan --no-ports             # skip port scanning
```

| Flag | Description |
|------|-------------|
| `--group` | Scan only IPs in this group |
| `--ip` | Comma-separated list of IPs to scan |
| `--no-ports` | Skip port scanning (host discovery only) |

**Output example:**

```
Scanning 12 IP(s)...

Results: 8 active, 3 uncertain, 1 available
```

---

## available

Get IPs that are safe to provision (quarantine complete).

```bash
ns-lite available --count 3
ns-lite available --group infra --count 5
ns-lite available --json-output
```

| Flag | Description |
|------|-------------|
| `--count` | Number of IPs to return (default: 10) |
| `--group` | Filter by group |
| `--json-output` | Output as JSON (for Terraform/API) |

**Output example:**

```
Available IPs (infra):
  10.0.0.20
  10.0.0.25
  10.0.0.12
```

**JSON output:**

```json
{
  "available_ips": ["10.0.0.20", "10.0.0.25", "10.0.0.12"],
  "count": 3
}
```

---

## groups

List all groups with their quarantine settings.

```bash
ns-lite groups
ns-lite groups --json-output
```

**Output example:**

```
Groups:
  infra       threshold=3  quarantine=48h
  database    threshold=5  quarantine=72h
  default     threshold=3  quarantine=48h
```

---

## status

Show detailed status for a specific IP.

```bash
ns-lite status 10.0.0.1
ns-lite status 10.0.0.1 --json-output
```

**Output example:**

```
IP:            10.0.0.1
Status:        ACTIVE_DETECTED
Hostname:      gateway-01
MAC:           aa:bb:cc:dd:ee:ff
Misses:        0
First seen:    2026-08-28 10:00:00
Last seen:     2026-08-28 12:00:00
Last scanned:  2026-08-28 12:00:00
```

---

## serve

Start the REST API server.

```bash
ns-lite serve
ns-lite serve --host 0.0.0.0 --port 9000
ns-lite serve --host 0.0.0.0 --port 8000 --workers 4
ns-lite serve --log-level debug
```

| Flag | Description |
|------|-------------|
| `--host` | Bind address (default: 127.0.0.1) |
| `--port` | Port number (default: 8000) |
| `--workers` | Number of gunicorn workers (default: 1) |
| `--log-level` | Log verbosity: debug, info, warning, error (default: info) |

!!! tip "Production"

    For production, use multiple workers and bind to all interfaces:

    ```bash
    ns-lite serve --host 0.0.0.0 --port 8000 --workers 4
    ```

See [API Reference](api.md) for all available endpoints.
