import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select
from netscan_lite.db import get_session
from netscan_lite.models import Group, IPAddress, IPStatus
from netscan_lite.scanner.runner import NmapScanner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class AvailableResponse(BaseModel):
    available_ips: List[str]
    count: int


class ScanRequest(BaseModel):
    group: Optional[str] = None
    ips: Optional[List[str]] = None


class ScanResponse(BaseModel):
    message: str
    scanned: int
    active: int
    uncertain: int
    available: int


class GroupResponse(BaseModel):
    id: str
    name: str
    miss_threshold: int
    quarantine_hours: int


@router.get("/available", response_model=AvailableResponse)
def get_available_ips(
    group: Optional[str] = None,
    count: int = Query(default=1, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Get next available IPs for provisioning."""
    query = select(IPAddress).where(IPAddress.status == IPStatus.AVAILABLE_CANDIDATE)

    if group:
        group_obj = session.exec(select(Group).where(Group.name == group)).first()
        if not group_obj:
            raise HTTPException(status_code=404, detail=f"Group '{group}' not found")
        query = query.where(IPAddress.group_id == group_obj.id)

    ips = session.exec(query.limit(count)).all()
    return AvailableResponse(available_ips=[i.ip for i in ips], count=len(ips))


@router.post("/scan", response_model=ScanResponse)
def trigger_scan(
    request: ScanRequest,
    session: Session = Depends(get_session),
):
    """Scan IPs for availability."""
    from netscan_lite.scanner.classifier import StateClassifier

    if request.group:
        group_obj = session.exec(select(Group).where(Group.name == request.group)).first()
        if not group_obj:
            raise HTTPException(status_code=404, detail=f"Group '{request.group}' not found")
        ips = session.exec(select(IPAddress).where(IPAddress.group_id == group_obj.id)).all()
        target_ips = [i.ip for i in ips]
    elif request.ips:
        target_ips = request.ips
        group_obj = None
    else:
        ips = session.exec(select(IPAddress)).all()
        target_ips = [i.ip for i in ips]
        group_obj = None

    if not target_ips:
        raise HTTPException(status_code=400, detail="No IPs to scan")

    scanner = NmapScanner()
    probe_results = asyncio.run(scanner.scan_targets(target_ips, scan_ports=True))

    now = datetime.now(timezone.utc)
    active = 0
    uncertain = 0
    available = 0

    for ip_str in target_ips:
        existing = session.exec(select(IPAddress).where(IPAddress.ip == ip_str)).first()
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

    return ScanResponse(
        message=f"Scanned {len(target_ips)} IP(s)",
        scanned=len(target_ips),
        active=active,
        uncertain=uncertain,
        available=available,
    )


@router.get("/groups", response_model=List[GroupResponse])
def list_groups(session: Session = Depends(get_session)):
    """List all groups."""
    groups = session.exec(select(Group)).all()
    return [
        GroupResponse(
            id=str(g.id),
            name=g.name,
            miss_threshold=g.miss_threshold,
            quarantine_hours=g.quarantine_hours,
        )
        for g in groups
    ]


@router.get("/ips/{ip_address}")
def get_ip_status(ip_address: str, session: Session = Depends(get_session)):
    """Get status of a specific IP."""
    ip_obj = session.exec(select(IPAddress).where(IPAddress.ip == ip_address)).first()
    if not ip_obj:
        raise HTTPException(status_code=404, detail=f"IP '{ip_address}' not found")

    return {
        "ip": ip_obj.ip,
        "status": ip_obj.status.value,
        "hostname": ip_obj.hostname,
        "mac_address": ip_obj.mac_address,
        "mac_vendor": ip_obj.mac_vendor,
        "consecutive_misses": ip_obj.consecutive_misses,
        "first_seen_at": str(ip_obj.first_seen_at) if ip_obj.first_seen_at else None,
        "last_seen_at": str(ip_obj.last_seen_at) if ip_obj.last_seen_at else None,
        "last_scanned_at": str(ip_obj.last_scanned_at) if ip_obj.last_scanned_at else None,
    }


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
