import ipaddress
import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, WebSocket, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlmodel import Session, func, select

from netscan_lite.auth import (
    TokenResponse,
    UserPayload,
    create_access_token,
    decode_access_token,
    get_current_user,
    ldap_authenticate,
)
from netscan_lite.config import settings
from netscan_lite.db import engine, get_session
from netscan_lite.models import Group, IPAddress, IPStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
ws_router = APIRouter()


def _escape_like(value: str) -> str:
    """Escape special characters for SQL LIKE patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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


class GroupDetailResponse(GroupResponse):
    description: Optional[str] = None
    ip_count: int


class GroupUpdateRequest(BaseModel):
    miss_threshold: Optional[int] = None
    quarantine_hours: Optional[int] = None
    description: Optional[str] = None


class StatsResponse(BaseModel):
    total_ips: int
    active: int
    uncertain: int
    available: int
    reserved: int
    groups: int
    last_scan: Optional[str] = None


class ImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: List[str]


class ReserveRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        allowed = {IPStatus.ASSIGNED_RESERVED.value, IPStatus.AVAILABLE_CANDIDATE.value}
        if v not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v


class IPListItem(BaseModel):
    ip: str
    status: str
    hostname: Optional[str] = None
    mac_address: Optional[str] = None
    mac_vendor: Optional[str] = None
    group_name: Optional[str] = None
    consecutive_misses: int = 0
    last_seen_at: Optional[str] = None
    last_scanned_at: Optional[str] = None


class IPListResponse(BaseModel):
    ips: List[IPListItem]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Token endpoint (outside /api prefix so it's at /token)
# ---------------------------------------------------------------------------

auth_router = APIRouter()


@auth_router.post("/token", response_model=TokenResponse, tags=["Auth"])
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """Authenticate via LDAP and get a JWT token."""
    user = await ldap_authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(username=user.username, dn=user.dn, groups=user.groups)
    return TokenResponse(access_token=token, username=user.username)


# ---------------------------------------------------------------------------
# Protected API endpoints
# ---------------------------------------------------------------------------


@router.get("/available", response_model=AvailableResponse, tags=["IPs"])
def get_available_ips(
    _user: UserPayload = Depends(get_current_user),
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


@router.post("/scan", response_model=ScanResponse, tags=["Scanning"])
async def trigger_scan(
    request: ScanRequest,
    _user: UserPayload = Depends(get_current_user),
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

    try:
        result = await scan_ips(target_ips, session, group=group_obj)
    except (TimeoutError, RuntimeError) as e:
        raise HTTPException(status_code=502, detail=f"Scan failed: {e}")

    return ScanResponse(
        message=f"Scanned {result['scanned']} IP(s)",
        scanned=result["scanned"],
        active=result["active"],
        uncertain=result["uncertain"],
        available=result["available"],
    )


@router.get("/groups", response_model=List[GroupResponse], tags=["Groups"])
def list_groups(
    _user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
):
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


@router.get("/ips", response_model=IPListResponse, tags=["IPs"])
def list_ips(
    _user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
    group: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    """List all IPs with filtering, search, and pagination."""
    query = select(IPAddress)

    if group:
        group_obj = session.exec(select(Group).where(Group.name == group)).first()
        if not group_obj:
            raise HTTPException(status_code=404, detail=f"Group '{group}' not found")
        query = query.where(IPAddress.group_id == group_obj.id)

    if status_filter:
        try:
            st = IPStatus(status_filter)
            query = query.where(IPAddress.status == st)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")

    if search:
        safe = _escape_like(search)
        search_pattern = f"%{safe}%"
        query = query.where((IPAddress.ip.like(search_pattern)) | (IPAddress.hostname.like(search_pattern)))

    total = len(session.exec(query).all())

    query = query.order_by(IPAddress.ip).offset((page - 1) * page_size).limit(page_size)
    ips = session.exec(query).all()

    # Resolve group names
    group_ids = {ip.group_id for ip in ips}
    groups_map = {}
    if group_ids:
        groups = session.exec(select(Group).where(Group.id.in_(group_ids))).all()
        groups_map = {g.id: g.name for g in groups}

    items = [
        IPListItem(
            ip=ip.ip,
            status=ip.status.value,
            hostname=ip.hostname,
            mac_address=ip.mac_address,
            mac_vendor=ip.mac_vendor,
            group_name=groups_map.get(ip.group_id),
            consecutive_misses=ip.consecutive_misses,
            last_seen_at=str(ip.last_seen_at) if ip.last_seen_at else None,
            last_scanned_at=str(ip.last_scanned_at) if ip.last_scanned_at else None,
        )
        for ip in ips
    ]

    return IPListResponse(ips=items, total=total, page=page, page_size=page_size)


@router.get("/ips/{ip_address}", tags=["IPs"])
def get_ip_status(
    ip_address: str,
    _user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get full status of a specific IP."""
    ip_obj = session.exec(select(IPAddress).where(IPAddress.ip == ip_address)).first()
    if not ip_obj:
        raise HTTPException(status_code=404, detail=f"IP '{ip_address}' not found")

    group = session.get(Group, ip_obj.group_id)

    return {
        "ip": ip_obj.ip,
        "status": ip_obj.status.value,
        "hostname": ip_obj.hostname,
        "mac_address": ip_obj.mac_address,
        "mac_vendor": ip_obj.mac_vendor,
        "open_ports": ip_obj.open_ports or [],
        "discovery_method": ip_obj.discovery_method,
        "consecutive_misses": ip_obj.consecutive_misses,
        "group_name": group.name if group else None,
        "first_seen_at": str(ip_obj.first_seen_at) if ip_obj.first_seen_at else None,
        "last_seen_at": str(ip_obj.last_seen_at) if ip_obj.last_seen_at else None,
        "last_scanned_at": str(ip_obj.last_scanned_at) if ip_obj.last_scanned_at else None,
    }


@router.post("/ips/{ip_address}/scan", response_model=ScanResponse, tags=["IPs"])
async def scan_single_ip(
    ip_address: str,
    _user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Scan a single IP."""
    ip_obj = session.exec(select(IPAddress).where(IPAddress.ip == ip_address)).first()
    if not ip_obj:
        raise HTTPException(status_code=404, detail=f"IP '{ip_address}' not found")

    from netscan_lite.scanner.service import scan_ips

    group = session.get(Group, ip_obj.group_id)
    try:
        result = await scan_ips([ip_address], session, group=group)
    except (TimeoutError, RuntimeError) as e:
        raise HTTPException(status_code=502, detail=f"Scan failed: {e}")

    return ScanResponse(
        message=f"Scanned {result['scanned']} IP(s)",
        scanned=result["scanned"],
        active=result["active"],
        uncertain=result["uncertain"],
        available=result["available"],
    )


# ---------------------------------------------------------------------------
# Dashboard endpoints
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=StatsResponse, tags=["Dashboard"])
def get_stats(
    _user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get dashboard overview stats."""
    total = session.exec(select(func.count(IPAddress.id))).one()
    active = session.exec(select(func.count(IPAddress.id)).where(IPAddress.status == IPStatus.ACTIVE_DETECTED)).one()
    uncertain = session.exec(
        select(func.count(IPAddress.id)).where(IPAddress.status == IPStatus.UNCERTAIN_FIREWALLED)
    ).one()
    available = session.exec(
        select(func.count(IPAddress.id)).where(IPAddress.status == IPStatus.AVAILABLE_CANDIDATE)
    ).one()
    reserved = session.exec(
        select(func.count(IPAddress.id)).where(IPAddress.status == IPStatus.ASSIGNED_RESERVED)
    ).one()
    group_count = session.exec(select(func.count(Group.id))).one()

    last_ip = session.exec(
        select(IPAddress).where(IPAddress.last_scanned_at.is_not(None)).order_by(IPAddress.last_scanned_at.desc())
    ).first()
    last_scan = str(last_ip.last_scanned_at) if last_ip and last_ip.last_scanned_at else None

    return StatsResponse(
        total_ips=total,
        active=active,
        uncertain=uncertain,
        available=available,
        reserved=reserved,
        groups=group_count,
        last_scan=last_scan,
    )


# ---------------------------------------------------------------------------
# Group management
# ---------------------------------------------------------------------------


@router.get("/groups-detail", response_model=List[GroupDetailResponse], tags=["Groups"])
def list_groups_detail(
    _user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List all groups with IP counts."""
    groups = session.exec(select(Group)).all()
    result = []
    for g in groups:
        ip_count = session.exec(select(func.count(IPAddress.id)).where(IPAddress.group_id == g.id)).one()
        result.append(
            GroupDetailResponse(
                id=str(g.id),
                name=g.name,
                description=g.description,
                miss_threshold=g.miss_threshold,
                quarantine_hours=g.quarantine_hours,
                ip_count=ip_count,
            )
        )
    return result


@router.put("/groups/{group_id}", response_model=GroupDetailResponse, tags=["Groups"])
def update_group(
    group_id: str,
    request: GroupUpdateRequest,
    _user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Update group quarantine settings."""
    import uuid

    try:
        gid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid group ID")

    group = session.get(Group, gid)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group '{group_id}' not found")

    if request.miss_threshold is not None:
        group.miss_threshold = request.miss_threshold
    if request.quarantine_hours is not None:
        group.quarantine_hours = request.quarantine_hours
    if request.description is not None:
        group.description = request.description

    session.add(group)
    session.commit()
    session.refresh(group)

    ip_count = session.exec(select(func.count(IPAddress.id)).where(IPAddress.group_id == group.id)).one()

    return GroupDetailResponse(
        id=str(group.id),
        name=group.name,
        description=group.description,
        miss_threshold=group.miss_threshold,
        quarantine_hours=group.quarantine_hours,
        ip_count=ip_count,
    )


@router.delete("/groups/{group_id}", status_code=204, tags=["Groups"])
def delete_group(
    group_id: str,
    _user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Delete a group and all its IPs."""
    import uuid

    try:
        gid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid group ID")

    group = session.get(Group, gid)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group '{group_id}' not found")

    session.delete(group)
    session.commit()


# ---------------------------------------------------------------------------
# IP reserve / release
# ---------------------------------------------------------------------------


@router.put("/ips/{ip_address}/reserve", tags=["IPs"])
def reserve_ip(
    ip_address: str,
    request: ReserveRequest,
    _user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Reserve or release an IP."""
    ip_obj = session.exec(select(IPAddress).where(IPAddress.ip == ip_address)).first()
    if not ip_obj:
        raise HTTPException(status_code=404, detail=f"IP '{ip_address}' not found")

    ip_obj.status = IPStatus(request.status)
    session.add(ip_obj)
    session.commit()
    session.refresh(ip_obj)

    return {
        "ip": ip_obj.ip,
        "status": ip_obj.status.value,
        "message": f"IP {ip_address} is now {request.status}",
    }


# ---------------------------------------------------------------------------
# File import
# ---------------------------------------------------------------------------


@router.post("/import", response_model=ImportResponse, tags=["Import"])
async def import_file(
    file: UploadFile,
    group: Optional[str] = None,
    _user: UserPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Import IPs from a CSV or XLSX file."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        raise HTTPException(status_code=400, detail="Only .csv and .xlsx files are supported")

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        from netscan_lite.importer import import_file as do_import

        result = do_import(tmp_path, session, group_name=group)
        return ImportResponse(
            imported=result["imported"],
            skipped=result["skipped"],
            errors=result["errors"],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# WebSocket — real-time scan progress
# ---------------------------------------------------------------------------


@ws_router.websocket("/ws/scan")
async def ws_scan(websocket: WebSocket):
    """WebSocket endpoint for real-time scan progress."""
    await websocket.accept()

    # Authenticate via query param
    token = websocket.query_params.get("token", "")
    if settings.LDAP_ENABLED:
        payload = decode_access_token(token)
        if payload is None:
            await websocket.close(code=4001, reason="Invalid or expired token")
            return
    elif not settings.DEV_AUTH_ENABLED:
        await websocket.close(code=4001, reason="Dev auth disabled")
        return
    # Dev mode: any token accepted

    try:
        data = await websocket.receive_json()
    except Exception:
        await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
        await websocket.close()
        return

    group_name = data.get("group")
    ips = data.get("ips")

    with Session(engine) as session:
        if group_name:
            group_obj = session.exec(select(Group).where(Group.name == group_name)).first()
            if not group_obj:
                await websocket.send_json({"type": "error", "detail": f"Group '{group_name}' not found"})
                await websocket.close()
                return
            all_ips = session.exec(select(IPAddress).where(IPAddress.group_id == group_obj.id)).all()
            target_ips = [i.ip for i in all_ips]
        elif ips:
            target_ips = ips
            group_obj = None
        else:
            all_ips = session.exec(select(IPAddress)).all()
            target_ips = [i.ip for i in all_ips]
            group_obj = None

        if not target_ips:
            await websocket.send_json({"type": "error", "detail": "No IPs to scan"})
            await websocket.close()
            return

        async def on_progress(msg: dict):
            try:
                await websocket.send_json(msg)
            except Exception:
                pass

        from netscan_lite.scanner.service import scan_ips

        try:
            result = await scan_ips(target_ips, session, group=group_obj, on_progress=on_progress)
            await websocket.send_json(
                {
                    "type": "complete",
                    "scanned": result["scanned"],
                    "active": result["active"],
                    "uncertain": result["uncertain"],
                    "available": result["available"],
                }
            )
        except (TimeoutError, RuntimeError) as e:
            await websocket.send_json({"type": "error", "detail": str(e)})

    await websocket.close()
