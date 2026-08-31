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

## Dashboard Development

The React dashboard lives inside `netscan_lite/dashboard/`. The built output goes to `netscan_lite/static/` (gitignored).

```bash
cd netscan_lite/dashboard
npm install           # first time only
npm run dev           # Vite dev server (http://localhost:5173)
npm run build         # builds to ../static/
npm run lint          # oxlint (NOT ruff — this is JS/TS)
```

After `npm run build`, the `static/` directory is served by FastAPI when you run `ns-lite serve`.

## Production Deployment

### Docker (recommended)

```bash
# Build and start with PostgreSQL
docker compose up -d

# Check logs
docker compose logs -f app

# Stop
docker compose down
```

### Bare Metal

```bash
pip install -e ".[xlsx]"

# Start with multiple workers
ns-lite serve --host 0.0.0.0 --port 8000 --workers 4

# Or single worker for dev
ns-lite serve
```

### Environment Variables for Production

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `LDAP_ENABLED` | Yes | Set to `true` for production auth |
| `LDAP_SERVER` | If LDAP enabled | LDAP server URL |
| `LDAP_BIND_DN` | If LDAP enabled | Service account DN |
| `LDAP_BIND_PASSWORD` | If LDAP enabled | Service account password |
| `JWT_SECRET_KEY` | Recommended | Token signing key (auto-generated if not set) |
| `WORKERS` | No | Gunicorn workers (default: 1) |
| `DB_PASSWORD` | If using docker-compose | PostgreSQL password |

### TLS / HTTPS

ns-lite runs plain HTTP. For production, place a reverse proxy in front:

**nginx:**
```nginx
server {
    listen 443 ssl;
    server_name ns-lite.internal;

    ssl_certificate /etc/ssl/certs/ns-lite.pem;
    ssl_certificate_key /etc/ssl/private/ns-lite.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Caddy (simpler):**
```
ns-lite.internal {
    reverse_proxy localhost:8000
}
```

Caddy auto-provisions TLS via Let's Encrypt.

## Architecture Map

```
netscan_lite/
  scanner/
    __init__.py
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
  static/           # built React dashboard (gitignored — run `npm run build` in dashboard/)
  dashboard/        # React SPA source (Vite + Tailwind, NOT gitignored)
    package.json    # npm scripts: dev, build, lint (oxlint), preview
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
- CI tests Python 3.10–3.13
- pytest config: `asyncio_mode = "auto"` in `pyproject.toml`

## Database Migrations

ns-lite uses Alembic for schema migrations. SQLite is the default for local dev; PostgreSQL for production.

### Creating a migration

After changing models in `models.py`:
```bash
python3 -m alembic revision --autogenerate -m "description of change"
python3 -m alembic upgrade head
```

### Applying migrations

```bash
python3 -m alembic upgrade head
```

### Rolling back

```bash
python3 -m alembic downgrade -1
```

### Migration files

Migrations live in `alembic/versions/`. Each has a revision ID and describes schema changes.

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

- `POST /scan` is synchronous — blocks until all nmap scans complete. Fine for current scale; would need background jobs for large batches.

## Code Conventions

- Type hints on all function signatures
- Keep functions small and focused
- Follow patterns already in the codebase
- No new dependencies without discussion
- No comments unless necessary; prefer clear naming
- ruff config: line-length=120, target Python 3.10 (`pyproject.toml`)

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
