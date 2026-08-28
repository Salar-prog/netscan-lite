# Configuration

ns-lite is configured via environment variables or a `.env` file in your working directory.

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./ns-lite.db` | Database connection URL |
| `DEBUG` | `false` | Enable debug logging |
| `DEFAULT_MISS_THRESHOLD` | `3` | Consecutive misses before marking uncertain |
| `DEFAULT_QUARANTINE_HOURS` | `48` | Hours an IP must stay uncertain before becoming available |
| `NMAP_TIMEOUT_SECONDS` | `300` | Timeout per scan in seconds |
| `NMAP_TIMING_TEMPLATE` | `-T4` | Nmap timing template |
| `TOP_TCP_PORTS` | `80,443,22,445,3389,8080,8443,53` | Ports to scan when port scanning is enabled |

### LDAP Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `LDAP_ENABLED` | `false` | Enable LDAP authentication |
| `LDAP_SERVER` | `ldap://localhost` | LDAP server URL |
| `LDAP_BIND_DN` | `cn=admin,dc=example,dc=com` | Service account DN for searching users |
| `LDAP_BIND_PASSWORD` | (empty) | Service account password |
| `LDAP_SEARCH_BASE` | `dc=example,dc=com` | Base DN for user search |
| `LDAP_SEARCH_FILTER` | `(sAMAccountName={username})` | Search filter (`{username}` is replaced) |
| `LDAP_STARTTLS` | `false` | Use StartTLS for connection |

### JWT Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | (auto-generated) | Secret key for signing tokens |
| `JWT_EXPIRY_HOURS` | `24` | Token lifetime in hours |

## Example .env

```bash
DATABASE_URL=sqlite:///./my-network.db
DEBUG=true
DEFAULT_MISS_THRESHOLD=5
DEFAULT_QUARANTINE_HOURS=24
NMAP_TIMEOUT_SECONDS=600
```

## Per-Group Settings

Quarantine thresholds (`miss_threshold` and `quarantine_hours`) are configured per-group, not globally. When you create a group (via import or API), it uses the `DEFAULT_MISS_THRESHOLD` and `DEFAULT_QUARANTINE_HOURS` values. After that, each group maintains its own settings.

This means your database servers can have a stricter quarantine (more misses, longer wait) than your app servers — if you configure them differently after import.

## Database

By default, ns-lite uses a SQLite database file (`ns-lite.db`) in the current directory. You can point it to any SQLModel-compatible database URL:

```bash
# PostgreSQL (if you need concurrent access)
DATABASE_URL=postgresql://user:pass@localhost/ns-lite

# Keep it simple
DATABASE_URL=sqlite:///./ns-lite.db
```

!!! note

    SQLite is fine for single-machine use. If you're running multiple ns-lite instances or need concurrent API access, consider PostgreSQL.

## Nmap Timing Templates

The `NMAP_TIMING_TEMPLATE` controls scan speed and stealth:

| Template | Speed | Stealth | Use Case |
|----------|-------|---------|----------|
| `-T0` | Very slow | Very high | IDS evasion |
| `-T1` | Slow | High | IDS evasion |
| `-T2` | Moderate | Moderate | Balanced |
| `-T3` | Normal | Normal | Default nmap |
| `-T4` | Fast | Low | **Recommended for ns-lite** |
| `-T5` | Very fast | Very low | Speed over stealth |

## Top Ports

The `TOP_TCP_PORTS` variable controls which ports are scanned. Default:

```
80,443,22,445,3389,8080,8443,53
```

Customize for your environment:

```bash
# Web servers only
TOP_TCP_PORTS=80,443,8080,8443

# Database servers
TOP_TCP_PORTS=3306,5432,1433,27017

# All common ports
TOP_TCP_PORTS=21,22,23,25,53,80,110,143,443,993,995,1433,3306,3389,5432,8080,8443
```
