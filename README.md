# ns-lite

[![CI](https://github.com/Salar-prog/netscan-lite/actions/workflows/ci.yml/badge.svg)](https://github.com/Salar-prog/netscan-lite/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Lightweight IP discovery with quarantine logic.

Extracted from [NetScan](https://github.com/Salar-prog/netscan) — scans specific IPs from CSV/XLSX files and tracks availability over time. No dashboard, no scheduler, no bloat.

## Features

- **CSV/XLSX import** — load IPs from spreadsheets
- **Targeted scanning** — scan only the IPs you specify
- **Hostname discovery** — captures hostnames via reverse DNS (requires PTR records)
- **Multi-probe detection** — uses ARP, ICMP, and TCP probes to determine host availability
- **Quarantine logic** — safe availability tracking (no false frees)
- **Groups** — organize IPs with per-group quarantine settings
- **CLI + API** — use from terminal or integrate with Terraform

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
ns-lite available --group infra --count 3  # get available IPs
ns-lite available --json-output            # JSON for Terraform
ns-lite groups                             # list groups
ns-lite status 10.0.0.1                    # check IP status
ns-lite serve                              # start API server
```

## CSV/XLSX Format

```csv
ip,hostname,group
10.0.0.1,gateway-01,infra
10.0.0.5,db-primary,database
10.0.0.12,,general
```

- `ip` — required, IPv4 address
- `hostname` — optional
- `group` — optional (default: "default")

## API

```bash
# Start server
ns-lite serve

# Get available IPs
curl "http://localhost:8000/api/available?group=infra&count=3"

# Trigger scan
curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{"group": "infra"}'

# Get IP status
curl http://localhost:8000/api/ips/10.0.0.1

# List groups
curl http://localhost:8000/api/groups
```

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
}
```

## Configuration

Environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./ns-lite.db` | Database URL |
| `DEBUG` | `false` | Debug logging |
| `DEFAULT_MISS_THRESHOLD` | `3` | Misses before uncertain |
| `DEFAULT_QUARANTINE_HOURS` | `48` | Hours before available |

## How Quarantine Works

1. **First scan**: IP responds → `ACTIVE_DETECTED`
2. **IP stops responding**: Status changes to `UNCERTAIN_FIREWALLED`
3. **Subsequent scans**: If IP keeps missing, `consecutive_misses` increments
4. **Quarantine complete**: After `miss_threshold` misses AND `quarantine_hours` elapsed → `AVAILABLE_CANDIDATE`

This prevents freeing an IP just because a firewall dropped a ping.

## Scanner Behavior

The scanner uses nmap with multiple probe types (ARP, ICMP echo/timestamp, TCP SYN/ACK) depending on
privilege level. The `discovery_method` field on each IP records which probe actually succeeded. Hostnames
are captured via reverse DNS (`-R` flag) and require PTR records to be configured on the target IPs.

## License

MIT
