import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlmodel import JSON, Column, Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IPStatus(str, Enum):
    ACTIVE_DETECTED = "ACTIVE_DETECTED"
    AVAILABLE_CANDIDATE = "AVAILABLE_CANDIDATE"
    ASSIGNED_RESERVED = "ASSIGNED_RESERVED"
    UNCERTAIN_FIREWALLED = "UNCERTAIN_FIREWALLED"


class EventType(str, Enum):
    DISCOVERED = "DISCOVERED"
    STATE_CHANGE = "STATE_CHANGE"
    RESERVED_TOGGLE = "RESERVED_TOGGLE"


# ---------------------------------------------------------------------------
# Database Tables
# ---------------------------------------------------------------------------


class Group(SQLModel, table=True):
    __tablename__ = "groups"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    miss_threshold: int = Field(default=3, description="Consecutive missed scans before eligible for available")
    quarantine_hours: int = Field(default=48, description="Minimum hours in UNCERTAIN before becoming AVAILABLE")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    ips: List["IPAddress"] = Relationship(back_populates="group", cascade_delete=True)


class IPAddress(SQLModel, table=True):
    __tablename__ = "ip_addresses"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: uuid.UUID = Field(foreign_key="groups.id", index=True)
    ip: str = Field(index=True, description="IPv4 address string")
    status: IPStatus = Field(default=IPStatus.AVAILABLE_CANDIDATE, index=True)
    hostname: Optional[str] = Field(default=None, index=True)
    mac_address: Optional[str] = Field(default=None, index=True)
    mac_vendor: Optional[str] = None
    open_ports: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    discovery_method: Optional[str] = None
    consecutive_misses: int = Field(default=0)
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    last_scanned_at: Optional[datetime] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    group: Optional[Group] = Relationship(back_populates="ips")
    history: List["IPHistory"] = Relationship(back_populates="ip_address", cascade_delete=True)


class IPHistory(SQLModel, table=True):
    __tablename__ = "ip_history"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ip_address_id: uuid.UUID = Field(foreign_key="ip_addresses.id", index=True)
    event_type: EventType = Field(index=True)
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    probe_details: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    timestamp: datetime = Field(default_factory=utc_now, index=True)

    ip_address: Optional[IPAddress] = Relationship(back_populates="history")


class ScanJob(SQLModel, table=True):
    __tablename__ = "scan_jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: uuid.UUID = Field(foreign_key="groups.id", index=True)
    target_ips: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = Field(default="QUEUED", index=True)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_ips: int = Field(default=0)
    active_ips: int = Field(default=0)
    uncertain_ips: int = Field(default=0)
    available_ips: int = Field(default=0)
    reserved_ips: int = Field(default=0)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
