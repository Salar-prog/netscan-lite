# Quick Start

Get up and running in 3 steps.

## 1. Create your IP list

Create a CSV file with your IPs:

```csv
ip,hostname,group
10.0.0.1,gateway-01,infra
10.0.0.5,db-primary,database
10.0.0.12,app-01,apps
10.0.0.20,,infra
10.0.0.25,monitoring,infra
```

- `ip` — required, IPv4 address
- `hostname` — optional, friendly name or reverse DNS
- `group` — optional, defaults to `"default"`

## 2. Import and scan

```bash
# Import IPs from CSV
ns-lite import --file ips.csv

# Scan all imported IPs
ns-lite scan
```

## 3. Get available IPs

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

## What just happened?

1. **Import** — IPs were added to the database, organized by group
2. **Scan** — nmap probed each IP using ARP/ICMP/TCP depending on your privileges
3. **Classify** — each IP was classified as active, uncertain, or available

The first scan establishes a baseline. Run `ns-lite scan` again later to update
the status of each IP.

## Next steps

- [CLI Reference](cli.md) — all available commands
- [API Reference](api.md) — REST API for automation
- [Configuration](config.md) — customize quarantine thresholds
