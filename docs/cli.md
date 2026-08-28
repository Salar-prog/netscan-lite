# CLI Reference

All commands are available as `ns-lite <command>`.

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

## available

Get IPs that are safe to provision.

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

## groups

List all groups with their quarantine settings.

```bash
ns-lite groups
ns-lite groups --json-output
```

## status

Show detailed status for a specific IP.

```bash
ns-lite status 10.0.0.1
ns-lite status 10.0.0.1 --json-output
```

## serve

Start the REST API server.

```bash
ns-lite serve
ns-lite serve --host 0.0.0.0 --port 9000
```

| Flag | Description |
|------|-------------|
| `--host` | Bind address (default: 127.0.0.1) |
| `--port` | Port number (default: 8000) |
