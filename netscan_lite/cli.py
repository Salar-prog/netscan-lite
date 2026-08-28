import asyncio
import ipaddress
import json
import logging
from pathlib import Path
from typing import Optional

import click
from sqlmodel import Session, select

from netscan_lite.db import engine, init_db
from netscan_lite.models import Group, IPAddress, IPStatus

logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug: bool):
    """ns-lite: Lightweight IP discovery with quarantine logic."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")
    init_db()


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--group", "-g", help="Override group name for all IPs in file")
def import_cmd(file_path: str, group: Optional[str]):
    """Import IPs from CSV or XLSX file.

    Expected columns: ip (required), hostname (optional), group (optional)
    """
    from netscan_lite.importer import import_file

    with Session(engine) as session:
        stats = import_file(Path(file_path), session, group)

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

        from netscan_lite.scanner.service import scan_ips
        result = asyncio.run(scan_ips(target_ips, session, group=group_obj, scan_ports=not no_ports))

        click.echo(
            f"\nResults: {result['active']} active, "
            f"{result['uncertain']} uncertain, {result['available']} available"
        )


@cli.command()
@click.option("--group", "-g", help="Filter by group name")
@click.option("--count", "-c", default=1, help="Number of available IPs to return")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def available(group: Optional[str], count: int, json_output: bool):
    """Get available IPs for provisioning."""
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
    with Session(engine) as session:
        all_groups = session.exec(select(Group)).all()
        if json_output:
            data = [{"name": g.name, "id": str(g.id), "miss_threshold": g.miss_threshold,
                     "quarantine_hours": g.quarantine_hours} for g in all_groups]
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
def serve(host: str, port: int):
    """Start the API server."""
    import uvicorn

    from netscan_lite.main import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()
