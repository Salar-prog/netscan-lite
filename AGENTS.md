# AGENTS.md

Guidance for AI coding agents and human collaborators working on ns-lite.

## Project Overview

ns-lite is a lightweight IP discovery tool with quarantine logic, extracted from NetScan. It scans specific IPs (from CSV/XLSX files) and tracks their availability over time.

- **Stack:** Python 3.10+, FastAPI, SQLModel (SQLite), Click CLI, React dashboard
- **No scheduler** — scans are on-demand only
- **CLI binary:** `ns-lite`
- **Docs site:** MkDocs Material at https://salar-prog.github.io/netscan-lite/

## Setup & Commands

```bash
# Install with all optional deps
pip install -e ".[xlsx,test,docs]"

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

# Lint & format
ruff check .
ruff format .

# Build docs
mkdocs serve
```

## Architecture Map

```
netscan_lite/
  scanner/
    runner.py       # nmap wrapper, scans list of IPs, XML parsing
    classifier.py   # quarantine state machine
    service.py      # scan orchestration (called by CLI + API)
  models.py         # Group, IPAddress (SQLModel tables)
  db.py             # SQLModel engine + session factory
  config.py         # minimal settings via pydantic-settings
  auth.py           # LDAP auth, JWT tokens, FastAPI dependencies
  importer.py       # CSV/XLSX parser
  cli.py            # click CLI (ns-lite binary)
  api.py            # FastAPI REST endpoints (router + WebSocket)
  main.py           # app entrypoint, static file serving
  static/           # built React dashboard (gitignored)
  dashboard/        # React SPA source (Vite + Tailwind)
    src/
      api.ts        # fetch wrapper + WebSocket client
      App.tsx       # router with protected routes
      components/   # Login, Dashboard, IpList, IpDetail, GroupManager, ScanTrigger, Import
  __init__.py       # package marker + version
```

## Testing

- Tests use in-memory SQLite (override `DATABASE_URL` in fixtures)
- Run with `pytest -v`
- No nmap required for tests (mock scanner)
- 84 tests covering: API, CLI, classifier, importer, scanner runner, dashboard API

## Scanner Behavior

- **Hostname resolution:** nmap is run with `-R` for reverse DNS. Hostnames are stored on `IPAddress.hostname`. Requires PTR records to be configured on the target IPs; returns `None` if no PTR exists.
- **Multi-probe detection:** The scanner does NOT rely on a single connection type. Depending on privilege level, it uses:
  - **Privileged (root/CAP_NET_RAW):** ARP ping (`-PR`), ICMP echo (`-PE`), ICMP timestamp (`-PP`), TCP SYN ping (`-PS`), SYN scan (`-sS`)
  - **Unprivileged:** ICMP echo (`-PE`), TCP ACK ping (`-PA`), TCP connect scan (`-sT`)
- The `discovery_method` field on each `IPAddress` records which probe actually succeeded: `ARP`, `ICMP`, `TCP_SYN`, or `TCP_CONNECT`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/token` | Login and get JWT token |
| `GET` | `/health` | Health check (no auth required) |
| `GET` | `/api/stats` | Dashboard overview stats |
| `GET` | `/api/groups` | List all groups with quarantine settings |
| `GET` | `/api/groups-detail` | List groups with IP counts |
| `PUT` | `/api/groups/{id}` | Update group quarantine settings |
| `DELETE` | `/api/groups/{id}` | Delete group and its IPs |
| `GET` | `/api/available` | Get available IPs (params: `group`, `count`) |
| `GET` | `/api/ips` | List IPs (paginated, filterable) |
| `GET` | `/api/ips/{ip}` | Get IP status with full details |
| `POST` | `/api/ips/{ip}/scan` | Scan a single IP |
| `PUT` | `/api/ips/{ip}/reserve` | Reserve or release an IP |
| `POST` | `/api/scan` | Trigger scan (body: `group` or `ips`) |
| `POST` | `/api/import` | Import IPs from CSV/XLSX |
| `WS` | `/ws/scan` | Real-time scan progress |

All endpoints except `/health` and `/token` require a valid JWT token in the `Authorization: Bearer <token>` header.

Request/response models are defined in `api.py` (`AvailableResponse`, `ScanRequest`, `ScanResponse`, `GroupResponse`, `StatsResponse`, `ImportResponse`, `IPListResponse`).

## Known Limitations

- `ScanJob` model defined in `models.py` but never used — scans return summary dicts, not persisted job records.

## Code Conventions

- Type hints on all function signatures
- Keep functions small and focused
- Follow patterns already in the codebase
- No new dependencies without discussion
- No comments unless necessary; prefer clear naming

## Domain Invariants (do not break)

1. **Safe availability logic** (`scanner/classifier.py`): an unresponsive host becomes `UNCERTAIN_FIREWALLED`; it may only become available after meeting **both** the consecutive-miss threshold *and* the quarantine duration. Never weaken this.
2. **Quarantine settings are per-Group**, not global. Each group has its own `miss_threshold` and `quarantine_hours`.
3. **IPs are unique within a Group** (DB-enforced via UniqueConstraint). Same IP can exist in multiple groups.
4. **Reserved IPs are locked**. An IP with status `ASSIGNED_RESERVED` stays reserved until explicitly released.

## Data Model

### Group

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `name` | string | Unique, indexed |
| `description` | string? | Optional description |
| `miss_threshold` | int | Consecutive misses before eligible (default: 3) |
| `quarantine_hours` | int | Hours in UNCERTAIN before AVAILABLE (default: 48) |

### IPAddress

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `group_id` | UUID | FK to Group |
| `ip` | string | IPv4 address |
| `status` | IPStatus | Current status enum |
| `hostname` | string? | Reverse DNS hostname |
| `mac_address` | string? | MAC address |
| `mac_vendor` | string? | MAC vendor lookup |
| `open_ports` | JSON | List of port dicts |
| `discovery_method` | string? | ARP/ICMP/TCP_SYN/TCP_CONNECT |
| `consecutive_misses` | int | Missed scans in a row |
| `first_seen_at` | datetime? | First successful scan |
| `last_seen_at` | datetime? | Last successful scan |
| `last_scanned_at` | datetime? | Last scan attempt |

Unique constraint: `(ip, group_id)`.

## CSV/XLSX Format

Expected columns:
- `ip` (required) — IPv4 address
- `hostname` (optional) — hostname or description
- `group` (optional) — group name (default: "default")

## Git Workflow

Use feature branches. Never push to `main` directly.

```bash
git checkout -b feat/your-feature
# make changes
pytest -v
ruff check . && ruff format --check .
git commit -m "feat: description"
git push origin feat/your-feature
```

## Further Reading

- [README.md](README.md) — usage, API examples, configuration
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to contribute
- [CHANGELOG.md](CHANGELOG.md) — version history
- [Docs site](https://salar-prog.github.io/netscan-lite/) — full documentation
- Source: extracted from [NetScan](https://github.com/Salar-prog/netscan)
