import asyncio
import json
import logging
from pathlib import Path
from typing import List, Optional
import click
from sqlmodel import Session, select
from netscan_lite.db import engine, init_db
from netscan_lite.models import Group, IPAddress, IPStatus
from netscan_lite.scanner.runner import NmapScanner

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
        scanner = NmapScanner()
        probe_results = asyncio.run(scanner.scan_targets(target_ips, scan_ports=not no_ports))
        click.echo(f"Got results for {len(probe_results)} host(s)")

        from netscan_lite.scanner.classifier import StateClassifier
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        active = 0
        uncertain = 0
        available = 0

        for ip_str in target_ips:
            existing = session.exec(
                select(IPAddress).where(IPAddress.ip == ip_str)
            ).first()

            probe = probe_results.get(ip_str)
            subnet_for_classify = group_obj or _get_or_create_default_group(session)

            outcome = StateClassifier.classify(
                ip=ip_str,
                existing=existing,
                probe=probe,
                subnet=subnet_for_classify,
                now=now,
            )

            if existing is None:
                ip_obj = IPAddress(
                    group_id=subnet_for_classify.id,
                    ip=ip_str,
                    status=outcome.new_status,
                    hostname=outcome.hostname,
                    mac_address=outcome.mac_address,
                    mac_vendor=outcome.mac_vendor,
                    open_ports=[
                        {"port": p.port, "protocol": p.protocol, "state": p.state,
                         "service": p.service, "product": p.product, "version": p.version}
                        for p in probe.open_ports
                    ] if probe else [],
                    discovery_method=outcome.discovery_method,
                    consecutive_misses=outcome.consecutive_misses,
                    first_seen_at=outcome.first_seen_at,
                    last_seen_at=outcome.last_seen_at,
                    last_scanned_at=outcome.last_scanned_at,
                )
                session.add(ip_obj)
            else:
                existing.status = outcome.new_status
                existing.hostname = outcome.hostname or existing.hostname
                existing.mac_address = outcome.mac_address or existing.mac_address
                existing.mac_vendor = outcome.mac_vendor or existing.mac_vendor
                existing.open_ports = [
                    {"port": p.port, "protocol": p.protocol, "state": p.state,
                     "service": p.service, "product": p.product, "version": p.version}
                    for p in probe.open_ports
                ] if probe else existing.open_ports
                existing.discovery_method = outcome.discovery_method
                existing.consecutive_misses = outcome.consecutive_misses
                existing.first_seen_at = outcome.first_seen_at
                existing.last_seen_at = outcome.last_seen_at
                existing.last_scanned_at = outcome.last_scanned_at
                existing.updated_at = now
                session.add(existing)

            if outcome.new_status == IPStatus.ACTIVE_DETECTED:
                active += 1
            elif outcome.new_status == IPStatus.UNCERTAIN_FIREWALLED:
                uncertain += 1
            elif outcome.new_status == IPStatus.AVAILABLE_CANDIDATE:
                available += 1

        session.commit()
        click.echo(f"\nResults: {active} active, {uncertain} uncertain, {available} available")


def _get_or_create_default_group(session: Session) -> Group:
    """Get or create the 'default' group."""
    existing = session.exec(select(Group).where(Group.name == "default")).first()
    if existing:
        return existing
    from netscan_lite.config import settings
    group = Group(
        name="default",
        miss_threshold=settings.DEFAULT_MISS_THRESHOLD,
        quarantine_hours=settings.DEFAULT_QUARANTINE_HOURS,
    )
    session.add(group)
    session.flush()
    return group


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
