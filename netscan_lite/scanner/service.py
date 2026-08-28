"""Shared scan service — called by both CLI and API."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Session, select

from netscan_lite.config import settings
from netscan_lite.models import Group, IPAddress, IPStatus
from netscan_lite.scanner.classifier import StateClassifier
from netscan_lite.scanner.runner import NmapScanner

logger = logging.getLogger(__name__)


def _get_or_create_default_group(session: Session) -> Group:
    existing = session.exec(select(Group).where(Group.name == "default")).first()
    if existing:
        return existing
    group = Group(
        name="default",
        miss_threshold=settings.DEFAULT_MISS_THRESHOLD,
        quarantine_hours=settings.DEFAULT_QUARANTINE_HOURS,
    )
    session.add(group)
    session.flush()
    return group


def scan_ips(
    ips: List[str],
    session: Session,
    group: Optional[Group] = None,
    scan_ports: bool = True,
) -> dict:
    """Scan a list of IPs, classify results, update DB. Returns summary."""
    if not ips:
        return {"scanned": 0, "active": 0, "uncertain": 0, "available": 0}

    scanner = NmapScanner()
    probe_results = asyncio.run(scanner.scan_targets(ips, scan_ports=scan_ports))

    now = datetime.now(timezone.utc)
    active = 0
    uncertain = 0
    available = 0

    for ip_str in ips:
        existing = session.exec(select(IPAddress).where(IPAddress.ip == ip_str)).first()
        probe = probe_results.get(ip_str)

        target_group = (
            group
            or (existing.group if existing and existing.group else None)
            or _get_or_create_default_group(session)
        )

        outcome = StateClassifier.classify(
            ip=ip_str,
            existing=existing,
            probe=probe,
            group=target_group,
            now=now,
        )

        if existing is None:
            ip_obj = IPAddress(
                group_id=target_group.id,
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

    return {"scanned": len(ips), "active": active, "uncertain": uncertain, "available": available}
