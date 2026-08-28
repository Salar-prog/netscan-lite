# AGENTS.md

Guidance for AI coding agents and human collaborators working on ns-lite.

## Project Overview

ns-lite is a lightweight IP discovery tool with quarantine logic, extracted from NetScan. It scans specific IPs (from CSV/XLSX files) and tracks their availability over time.

- **Stack:** Python 3.10+, FastAPI, SQLModel (SQLite), Click CLI
- **No scheduler** — scans are on-demand only
- **No dashboard** — API + CLI interface
- **CLI binary:** `ns-lite`

## Setup & Commands

```bash
# Install with xlsx support
pip install -e ".[xlsx]"

# Import IPs from CSV/XLSX
ns-lite import --file ips.csv
ns-lite import --file ips.xlsx --group infra

# Scan IPs
ns-lite scan --group infra
ns-lite scan --ip 10.0.0.1,10.0.0.5
ns-lite scan  # scan all IPs

# Get available IPs for provisioning
ns-lite available --group infra --count 3
ns-lite available --json-output

# Start API server
ns-lite serve

# Run tests
pytest -v
```

## Architecture Map

```
netscan_lite/
  scanner/
    runner.py       # nmap wrapper, scans list of IPs
    classifier.py   # quarantine state machine
    cidr.py         # CIDR utilities
  models.py         # Group, IPAddress, IPHistory, ScanJob
  db.py             # SQLModel engine + create_all
  config.py         # minimal settings via pydantic-settings
  importer.py       # CSV/XLSX parser
  cli.py            # click CLI (ns-lite binary)
  api.py            # thin FastAPI wrapper
  main.py           # app entrypoint
  __init__.py       # package marker
```

## Testing

- Tests use in-memory SQLite (override `DATABASE_URL` in fixtures)
- Run with `pytest -v`
- No nmap required for tests (mock scanner)

## Code Conventions

- Type hints on all function signatures
- Keep functions small and focused
- Follow patterns already in the codebase
- No new dependencies without discussion
- No comments unless necessary; prefer clear naming

## Domain Invariants (do not break)

1. **Safe availability logic** (`scanner/classifier.py`): an unresponsive host becomes `UNCERTAIN_FIREWALLED`; it may only become available after meeting **both** the consecutive-miss threshold *and* the quarantine duration. Never weaken this.
2. **Quarantine settings are per-Group**, not global. Each group has its own `miss_threshold` and `quarantine_hours`.
3. **IPs are unique within a Group**. Same IP can exist in multiple groups.
4. **Reserved IPs are locked**. An IP with status `ASSIGNED_RESERVED` stays reserved until explicitly released.

## CSV/XLSX Format

Expected columns:
- `ip` (required) — IPv4 address
- `hostname` (optional) — hostname or description
- `group` (optional) — group name (default: "default")

Example:
```csv
ip,hostname,group
10.0.0.1,gateway-01,infra
10.0.0.5,db-primary,database
10.0.0.12,,general
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/available` | Get available IPs (params: `group`, `count`) |
| `POST` | `/api/scan` | Trigger scan (body: `group` or `ips`) |
| `GET` | `/api/groups` | List all groups |
| `GET` | `/api/ips/{ip}` | Get IP status |
| `GET` | `/health` | Health check |

## Configuration

Environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./ns-lite.db` | Database URL |
| `DEBUG` | `false` | Debug logging |
| `DEFAULT_MISS_THRESHOLD` | `3` | Consecutive misses before uncertain |
| `DEFAULT_QUARANTINE_HOURS` | `48` | Hours in uncertain before available |
| `NMAP_TIMEOUT_SECONDS` | `300` | Per-scan timeout |
| `NMAP_TIMING_TEMPLATE` | `-T4` | Nmap timing |
| `TOP_TCP_PORTS` | `80,443,22,445,3389,8080,8443,53` | Ports to scan |

## Git Workflow

Use feature branches. Never push to `main` directly.

```bash
git checkout -b feat/your-feature
# make changes
pytest -v
git commit -m "feat: description"
git push origin feat/your-feature
```

## Further Reading

- [README.md](README.md) — usage and examples
- Source: extracted from [NetScan](https://github.com/Salar-prog/netscan)
