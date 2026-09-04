# Production Deployment

This guide covers all deployment options for ns-lite, from Docker to bare metal.

## Prerequisites

Before deploying, ensure you have:

- **nmap** installed on the host machine (required for scanning)
- **Python 3.10+** (for bare metal installation)
- **Docker + Docker Compose** (for containerized deployment)
- **PostgreSQL** (recommended for production; SQLite works for single-machine dev)
- **LDAP server** (optional, for enterprise authentication)

## Option 1: Docker Compose (Recommended)

Docker Compose is the simplest way to deploy ns-lite with PostgreSQL.

### Quick Start

```bash
# Clone the repository
git clone https://github.com/Salar-prog/netscan-lite.git
cd netscan-lite

# Create a .env file (see Configuration section below)
cp .env.example .env
# Edit .env with your settings

# Start everything
docker compose up -d
```

This starts:

- **ns-lite app** on port 8000
- **PostgreSQL** on port 5432

### Configuration

Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql://netscan:your-password@db:5432/netscan
DB_PASSWORD=your-password

# Authentication (choose one)
LDAP_ENABLED=true
LDAP_SERVER=ldap://your-ldap-server
LDAP_BIND_DN=cn=service-account,dc=example,dc=com
LDAP_BIND_PASSWORD=your-ldap-password
LDAP_SEARCH_BASE=dc=example,dc=com
LDAP_SEARCH_FILTER=(sAMAccountName={username})
LDAP_USE_SSL=true

# Security
JWT_SECRET_KEY=generate-a-random-key-here
DEBUG=false

# Authorization
ADMIN_GROUPS=["ns-lite-admins"]

# Server
WORKERS=4
```

### Managing the Deployment

```bash
# Start
docker compose up -d

# Stop
docker compose down

# View logs
docker compose logs -f app

# Restart after config changes
docker compose restart app

# Check health
curl http://localhost:8000/health
```

### Data Persistence

PostgreSQL data is stored in a Docker volume named `pgdata`. To back up:

```bash
# Backup
docker compose exec db pg_dump -U netscan netscan > backup.sql

# Restore
cat backup.sql | docker compose exec -T db psql -U netscan netscan
```

### Database Backup/Restore (CLI)

ns-lite provides built-in backup and restore commands:

```bash
# Backup (SQLite: file copy, PostgreSQL: pg_dump -Fc)
ns-lite db backup                          # auto-generated timestamped filename
ns-lite db backup -o my-backup.db          # specific output file

# Restore
ns-lite db restore ns-lite-backup-20260904T120000Z.db
ns-lite db restore ns-lite-backup-20260904T120000Z.db --yes  # skip confirmation
```

For PostgreSQL, these commands use `pg_dump`/`pg_restore` (requires `postgresql-client` installed).

### Customizing PostgreSQL

To use an external PostgreSQL instance, update `DATABASE_URL` in your `.env`:

```bash
DATABASE_URL=postgresql://user:password@external-host:5432/dbname
```

Then remove the `db` service from `docker-compose.yml` or set `DB_PASSWORD` to match.

## Option 2: Docker Standalone

Build and run the Docker image directly.

### Build the Image

```bash
docker build -t ns-lite:latest .
```

The Dockerfile includes:

1. **Node.js stage** — builds the React dashboard
2. **Python builder** — installs Python dependencies
3. **Runtime** — minimal image with nmap + curl

### Run with Environment Variables

```bash
docker run -d \
  --name ns-lite \
  -p 8000:8000 \
  --net=host \
  -e DATABASE_URL=postgresql://user:pass@host/db \
  -e LDAP_ENABLED=true \
  -e LDAP_SERVER=ldap://your-server \
  -e LDAP_BIND_DN=cn=admin,dc=example,dc=com \
  -e LDAP_BIND_PASSWORD=secret \
  -e LDAP_SEARCH_BASE=dc=example,dc=com \
  -e DEBUG=false \
  -e WORKERS=4 \
  ns-lite:latest
```

!!! warning "Network Mode"

    Use `--net=host` for scanning to work properly. ARP and ICMP probes require access to the host network.

### Scanning from Docker

For network scanning, the container needs:

```bash
# Option 1: Host networking (simplest)
docker run --net=host ns-lite:latest scan --group infra

# Option 2: Privileged mode (if --net=host doesn't work)
docker run --privileged ns-lite:latest scan --group infra
```

## Option 3: Bare Metal

Install and run directly on a Linux server.

### Installation

```bash
# From PyPI (when published)
pip install "netscan-lite[xlsx,postgres]"

# From source
git clone https://github.com/Salar-prog/netscan-lite.git
cd netscan-lite
pip install -e ".[xlsx,postgres]"
```

### Systemd Service

ns-lite ships a systemd unit file at `deploy/ns-lite.service`. Install it:

```bash
sudo bash deploy/install.sh
```

This creates a dedicated `ns-lite` user, installs into `/opt/ns-lite/`, and sets up the systemd service with security hardening (`NoNewPrivileges`, `ProtectSystem=strict`, `AmbientCapabilities=CAP_NET_RAW`).

Or manually copy the service file:

```bash
cp deploy/ns-lite.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ns-lite
```

Configure `/opt/ns-lite/.env` with your settings, then:

```bash
sudo systemctl start ns-lite
```

### Running Directly

```bash
# Set environment variables
export DATABASE_URL=postgresql://user:password@localhost/netscan
export LDAP_ENABLED=true
# ... other env vars

# Start with gunicorn (production)
ns-lite serve --host 0.0.0.0 --port 8000 --workers 4

# Or single worker (development)
ns-lite serve
```

### Log Management

Logs go to stdout/stderr. For systemd, view with:

```bash
journalctl -u ns-lite -f
```

For Docker:

```bash
docker logs -f ns-lite
```

## Database Setup

### PostgreSQL (Recommended)

**Using docker-compose:** PostgreSQL is included automatically.

**Manual setup:**

```bash
# Create database and user
sudo -u postgres psql
CREATE USER netscan WITH PASSWORD 'your-password';
CREATE DATABASE netscan OWNER netscan;
GRANT ALL PRIVILEGES ON DATABASE netscan TO netscan;
\q
```

Set the connection string:

```bash
export DATABASE_URL=postgresql://netscan:your-password@localhost/netscan
```

### Running Migrations

ns-lite uses Alembic for database migrations. On first deploy:

```bash
# Apply all migrations
ns-lite db upgrade
```

For new deployments, `init_db()` in `db.py` creates tables automatically. Use Alembic for schema changes after initial setup.

### SQLite vs PostgreSQL

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Setup | Zero config | Requires server |
| Concurrency | Single writer | Multiple writers |
| Backups | Copy file | pg_dump/pg_restore |
| Best for | Dev, single user | Production, multi-user |

!!! note

    SQLite works fine for development and single-machine deployments. Use PostgreSQL for production with multiple API consumers or concurrent scans.

### Connection Pooling

When using PostgreSQL, ns-lite configures connection pooling automatically:

- **pool_size:** 5 connections
- **max_overflow:** 10 additional connections
- **pool_timeout:** 30 seconds
- **pool_recycle:** 1800 seconds (30 minutes)

## Security Hardening

### LDAP Configuration

For production, always use LDAP authentication:

```bash
LDAP_ENABLED=true
LDAP_SERVER=ldaps://ldap.example.com:636  # Use LDAPS
LDAP_BIND_DN=cn=ns-lite-service,dc=example,dc=com
LDAP_BIND_PASSWORD=your-secure-password
LDAP_SEARCH_BASE=dc=example,dc=com
LDAP_SEARCH_FILTER=(sAMAccountName={username})
LDAP_USE_SSL=true
```

!!! warning "Dev Auth"

    Never set `DEV_AUTH_ENABLED=true` in production. When `DEBUG=false`, dev auth is rejected even if enabled.

### TLS/HTTPS

ns-lite runs plain HTTP. Always place a reverse proxy in front.

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

### JWT Secret

Generate a secure JWT secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set it in your environment:

```bash
JWT_SECRET_KEY=your-generated-secret-here
```

If not set, ns-lite auto-generates one and persists it to `~/.ns-lite/jwt-secret`. In containers, mount this path as a volume to persist across restarts.

### Firewall Rules

```bash
# Allow HTTPS (if using reverse proxy)
sudo ufw allow 443/tcp

# Allow HTTP (if not using reverse proxy)
sudo ufw allow 8000/tcp

# Allow SSH for management
sudo ufw allow 22/tcp
```

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Returns:

```json
{"status": "healthy", "service": "ns-lite"}
```

The health check verifies database connectivity. Returns 503 if the database is unreachable.

### Readiness Probe

```bash
curl http://localhost:8000/health/ready
```

Returns 200 if the service is ready to accept traffic (database reachable and nmap available). Returns 503 if nmap is not installed or the database is unreachable. Use this for Kubernetes readiness probes or load balancer health checks.

### Docker Health Check

The Docker image includes a built-in health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

### Log Levels

Control log verbosity with the `--log-level` flag:

```bash
ns-lite serve --log-level debug    # Verbose
ns-lite serve --log-level info     # Default
ns-lite serve --log-level warning  # Quiet
ns-lite serve --log-level error    # Errors only
```

Or set via environment:

```bash
LOG_LEVEL=debug
```

## Troubleshooting

### Common Issues

**"Dev auth requires DEBUG=true"**

You're trying to use dev auth without `DEBUG=true`. Either:

- Set `DEBUG=true` (development only)
- Set `LDAP_ENABLED=true` and configure LDAP

**"No IPs to scan"**

Import IPs first:

```bash
ns-lite import-cmd your-ips.csv
```

**Health check returns 503**

Database is unreachable. Check:

1. PostgreSQL is running
2. `DATABASE_URL` is correct
3. Network connectivity between app and database

**Scanning doesn't work in Docker**

Use `--net=host` or `--privileged` mode. See [Scanning from Docker](#scanning-from-docker).

### Debug Mode

Enable debug mode for verbose logging:

```bash
DEBUG=true ns-lite serve
```

!!! warning

    Never use `DEBUG=true` in production. It disables security features and enables verbose logging.

## Next Steps

- [Configuration Reference](config.md) — all environment variables
- [CLI Reference](cli.md) — all commands and flags
- [API Reference](api.md) — REST API with examples
