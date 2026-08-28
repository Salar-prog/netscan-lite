import ipaddress
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from netscan_lite.db import get_session
from netscan_lite.models import Group, IPAddress, IPStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class AvailableResponse(BaseModel):
    available_ips: List[str]
    count: int


class ScanRequest(BaseModel):
    group: Optional[str] = None
    ips: Optional[List[str]] = None

    @field_validator("ips")
    @classmethod
    def validate_ips(cls, v):
        if v is not None:
            for ip in v:
                try:
                    ipaddress.IPv4Address(ip.strip())
                except ValueError:
                    raise ValueError(f"Invalid IPv4 address: {ip}")
        return v


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

    from netscan_lite.scanner.service import scan_ips
    result = scan_ips(target_ips, session, group=group_obj)

    return ScanResponse(
        message=f"Scanned {result['scanned']} IP(s)",
        scanned=result["scanned"],
        active=result["active"],
        uncertain=result["uncertain"],
        available=result["available"],
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
