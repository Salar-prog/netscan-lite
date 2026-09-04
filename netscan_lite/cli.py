import asyncio
import ipaddress
import json
import logging
from pathlib import Path
from typing import Optional

import click
from sqlmodel import Session, select

from netscan_lite.db import engine, init_db
from netscan_lite.logging_config import audit, setup_logging
from netscan_lite.models import Group, IPAddress, IPStatus

logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug: bool):
    """ns-lite: Lightweight IP discovery with quarantine logic."""
    setup_logging(log_level="debug" if debug else "info")
    init_db()


@cli.command("import-cmd")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--group", "-g", help="Override group name for all IPs in file")
def import_cmd(file_path: str, group: Optional[str]):
    """Import IPs from CSV or XLSX file.

    Expected columns: ip (required), hostname (optional), group (optional)
    """
    from netscan_lite.importer import import_file

    audit("cli_import", user="cli", detail=f"file={file_path} group={group or 'auto'}")
    with Session(engine) as session:
        stats = import_file(Path(file_path), session, group)

    audit("cli_import_complete", user="cli", detail=f"imported={stats['imported']} skipped={stats['skipped']}")
    click.echo(f"Imported: {stats['imported']}")
    click.echo(f"Skipped: {stats['skipped']}")
    if stats["errors"]:
        click.echo("Errors:")
        for err in stats["errors"]:
            click.echo(f"  - {err}")


@cli.command()
@click.option("--group", "-g", help="Group name to scan")
@click.option("--ip", "-i", help="Comma-separated list of specific IPs to scan")
@click.option("--no-ports", is_flag=True, help="Skip port scanning (host discovery only)")
def scan(group: Optional[str], ip: Optional[str], no_ports: bool):
    """Scan IPs for availability.

    Provide either --group or --ip. If neither, scans all IPs.
    """
    with Session(engine) as session:
        if ip:
            target_ips = [i.strip() for i in ip.split(",") if i.strip()]
            for ip_str in target_ips:
                try:
                    ipaddress.IPv4Address(ip_str)
                except ValueError:
                    click.echo(f"Invalid IP address: {ip_str}", err=True)
                    raise SystemExit(1)
            group_obj = None
        elif group:
            group_obj = session.exec(select(Group).where(Group.name == group)).first()
            if not group_obj:
                click.echo(f"Group '{group}' not found", err=True)
                raise SystemExit(1)
            ips = session.exec(select(IPAddress).where(IPAddress.group_id == group_obj.id)).all()
            target_ips = [i.ip for i in ips]
        else:
            ips = session.exec(select(IPAddress)).all()
            target_ips = [i.ip for i in ips]

        if not target_ips:
            click.echo("No IPs to scan", err=True)
            return

        click.echo(f"Scanning {len(target_ips)} IP(s)...")
        audit("cli_scan", user="cli", detail=f"group={group or 'all'} targets={len(target_ips)}")

        from netscan_lite.scanner.service import scan_ips

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            click.echo("Error: cannot run scan from inside an async context", err=True)
            raise SystemExit(1)
        try:
            result = asyncio.run(scan_ips(target_ips, session, group=group_obj, scan_ports=not no_ports))
        except (TimeoutError, RuntimeError) as e:
            click.echo(f"Scan error: {e}", err=True)
            audit("cli_scan", user="cli", result="error", detail=f"error={e}")
            raise SystemExit(1)

        audit(
            "cli_scan_complete",
            user="cli",
            detail=f"scanned={result['scanned']} active={result['active']} "
            f"uncertain={result['uncertain']} available={result['available']}",
        )
        click.echo(
            f"\nResults: {result['active']} active, {result['uncertain']} uncertain, {result['available']} available"
        )


@cli.command()
@click.option("--group", "-g", help="Filter by group name")
@click.option("--count", "-c", default=1, help="Number of available IPs to return")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def available(group: Optional[str], count: int, json_output: bool):
    """Get available IPs for provisioning."""
    audit("cli_available", user="cli", detail=f"group={group or 'all'} count={count}")
    with Session(engine) as session:
        query = select(IPAddress).where(IPAddress.status == IPStatus.AVAILABLE_CANDIDATE)

        if group:
            group_obj = session.exec(select(Group).where(Group.name == group)).first()
            if not group_obj:
                click.echo(f"Group '{group}' not found", err=True)
                raise SystemExit(1)
            query = query.where(IPAddress.group_id == group_obj.id)

        ips = session.exec(query.limit(count)).all()
        result = [i.ip for i in ips]

        audit("cli_available_complete", user="cli", detail=f"returned={len(result)}")
        if json_output:
            click.echo(json.dumps({"available_ips": result, "count": len(result)}))
        else:
            if result:
                for ip in result:
                    click.echo(ip)
            else:
                click.echo("No available IPs found")


@cli.command()
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def groups(json_output: bool):
    """List all groups."""
    audit("cli_groups", user="cli")
    with Session(engine) as session:
        all_groups = session.exec(select(Group)).all()
        audit("cli_groups_complete", user="cli", detail=f"count={len(all_groups)}")
        if json_output:
            data = [
                {
                    "name": g.name,
                    "id": str(g.id),
                    "miss_threshold": g.miss_threshold,
                    "quarantine_hours": g.quarantine_hours,
                }
                for g in all_groups
            ]
            click.echo(json.dumps(data, indent=2))
        else:
            if not all_groups:
                click.echo("No groups found")
                return
            for g in all_groups:
                click.echo(f"{g.name} (miss_threshold={g.miss_threshold}, quarantine_hours={g.quarantine_hours})")


@cli.command()
@click.argument("ip_address")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def status(ip_address: str, json_output: bool):
    """Show status of a specific IP."""
    audit("cli_status", user="cli", detail=f"ip={ip_address}")
    with Session(engine) as session:
        ip_obj = session.exec(select(IPAddress).where(IPAddress.ip == ip_address)).first()
        if not ip_obj:
            click.echo(f"IP '{ip_address}' not found", err=True)
            raise SystemExit(1)

        if json_output:
            data = {
                "ip": ip_obj.ip,
                "status": ip_obj.status.value,
                "hostname": ip_obj.hostname,
                "mac_address": ip_obj.mac_address,
                "consecutive_misses": ip_obj.consecutive_misses,
                "first_seen_at": str(ip_obj.first_seen_at) if ip_obj.first_seen_at else None,
                "last_seen_at": str(ip_obj.last_seen_at) if ip_obj.last_seen_at else None,
                "last_scanned_at": str(ip_obj.last_scanned_at) if ip_obj.last_scanned_at else None,
            }
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"IP:        {ip_obj.ip}")
            click.echo(f"Status:    {ip_obj.status.value}")
            click.echo(f"Hostname:  {ip_obj.hostname or '-'}")
            click.echo(f"MAC:       {ip_obj.mac_address or '-'}")
            click.echo(f"Misses:    {ip_obj.consecutive_misses}")
            click.echo(f"Last seen: {ip_obj.last_seen_at or '-'}")
            click.echo(f"Scanned:   {ip_obj.last_scanned_at or '-'}")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8000, type=int, help="Bind port")
@click.option("--workers", default=1, type=int, help="Number of uvicorn workers (1 = single-process dev mode)")
@click.option("--log-level", default="info", type=click.Choice(["debug", "info", "warning", "error"]), help="Log level")
def serve(host: str, port: int, workers: int, log_level: str):
    """Start the API server."""
    from netscan_lite.main import create_app

    audit("cli_serve", user="cli", detail=f"host={host} port={port} workers={workers}")
    app = create_app()

    if workers > 1:
        import gunicorn.app.base

        class StandaloneApplication(gunicorn.app.base.BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        options = {
            "bind": f"{host}:{port}",
            "workers": workers,
            "worker_class": "uvicorn.workers.UvicornWorker",
            "loglevel": log_level,
        }
        StandaloneApplication(app, options).run()
    else:
        import uvicorn

        uvicorn.run(app, host=host, port=port, log_level=log_level)


@cli.group()
def db():
    """Database migration commands (Alembic)."""
    pass


@db.command("upgrade")
@click.argument("revision", default="head")
def db_upgrade(revision: str):
    """Upgrade database to a revision (default: head)."""
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, revision)
    click.echo(f"Database upgraded to {revision}")


@db.command("downgrade")
@click.argument("revision", default="-1")
def db_downgrade(revision: str):
    """Downgrade database by one revision (default: -1)."""
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.downgrade(alembic_cfg, revision)
    click.echo(f"Database downgraded to {revision}")


@db.command("migrate")
@click.option("-m", "--message", required=True, help="Migration message")
def db_migrate(message: str):
    """Generate a new migration from model changes."""
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message=message)
    click.echo(f"Migration created: {message}")


@db.command("current")
def db_current():
    """Show current revision."""
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.current(alembic_cfg)


@db.command("history")
def db_history():
    """Show migration history."""
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.history(alembic_cfg)


@cli.command()
@click.option("--username", "-u", prompt="Username", help="LDAP username")
@click.option("--password", "-p", prompt=True, hide_input=True, help="LDAP password")
@click.option("--server", "-s", default=None, help="API server URL (default: http://127.0.0.1:8000)")
def auth(username: str, password: str, server: Optional[str]):
    """Authenticate and store a JWT token for API access.

    The token is saved to ~/.ns-lite/token and used automatically by
    other ns-lite commands when LDAP is enabled.
    """
    import urllib.request

    from netscan_lite.config import settings

    audit("cli_auth", user=username, detail=f"server={server or settings.API_BASE_URL}")

    # Determine API base URL: --server flag > env var > default
    api_base = server or settings.API_BASE_URL

    # Login via the API's /token endpoint
    data = urllib.parse.urlencode({"username": username, "password": password}).encode()
    req = urllib.request.Request(f"{api_base}/token", data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            click.echo("Authentication failed: invalid username or password", err=True)
            audit("cli_auth", user=username, result="error", detail="invalid credentials")
            raise SystemExit(1)
        click.echo(f"Authentication failed: {e}", err=True)
        audit("cli_auth", user=username, result="error", detail=f"http_error={e.code}")
        raise SystemExit(1)
    except urllib.error.URLError as e:
        click.echo(f"Cannot reach API server at {api_base}: {e}", err=True)
        click.echo("Make sure the API server is running: ns-lite serve", err=True)
        audit("cli_auth", user=username, result="error", detail=f"connection_error={e}")
        raise SystemExit(1)

    # Save token to ~/.ns-lite/token
    token_dir = Path.home() / ".ns-lite"
    token_dir.mkdir(parents=True, exist_ok=True)
    token_file = token_dir / "token"
    token_file.write_text(result["access_token"])
    token_file.chmod(0o600)

    audit("cli_auth_complete", user=username, detail=f"expires_in={settings.JWT_EXPIRY_HOURS}h")
    click.echo(f"Authenticated as {result['username']}")
    click.echo(f"Token saved to {token_file}")
    click.echo(f"Expires in {settings.JWT_EXPIRY_HOURS} hours")


if __name__ == "__main__":
    cli()
