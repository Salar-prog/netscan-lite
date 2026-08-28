"""Basic tests for ns-lite."""

import pytest
from sqlmodel import Session, select

from netscan_lite.models import Group, IPAddress, IPStatus


def test_group_creation(session: Session):
    """Test creating a group."""
    group = Group(name="test-group", miss_threshold=3, quarantine_hours=48)
    session.add(group)
    session.commit()
    session.refresh(group)

    assert group.name == "test-group"
    assert group.miss_threshold == 3
    assert group.quarantine_hours == 48
    assert group.id is not None


def test_ip_creation(session: Session):
    """Test creating an IP address."""
    group = Group(name="test-group")
    session.add(group)
    session.flush()

    ip = IPAddress(
        group_id=group.id,
        ip="10.0.0.1",
        status=IPStatus.AVAILABLE_CANDIDATE,
        hostname="test-host",
    )
    session.add(ip)
    session.commit()
    session.refresh(ip)

    assert ip.ip == "10.0.0.1"
    assert ip.status == IPStatus.AVAILABLE_CANDIDATE
    assert ip.hostname == "test-host"
    assert ip.group_id == group.id


def test_ip_status_transitions(session: Session):
    """Test IP status transitions."""
    group = Group(name="test-group")
    session.add(group)
    session.flush()

    ip = IPAddress(
        group_id=group.id,
        ip="10.0.0.2",
        status=IPStatus.AVAILABLE_CANDIDATE,
    )
    session.add(ip)
    session.commit()

    # Transition to active
    ip.status = IPStatus.ACTIVE_DETECTED
    session.add(ip)
    session.commit()
    session.refresh(ip)
    assert ip.status == IPStatus.ACTIVE_DETECTED

    # Transition to uncertain
    ip.status = IPStatus.UNCERTAIN_FIREWALLED
    session.add(ip)
    session.commit()
    session.refresh(ip)
    assert ip.status == IPStatus.UNCERTAIN_FIREWALLED

    # Transition back to available
    ip.status = IPStatus.AVAILABLE_CANDIDATE
    session.add(ip)
    session.commit()
    session.refresh(ip)
    assert ip.status == IPStatus.AVAILABLE_CANDIDATE


def test_importer_csv(session: Session, tmp_path):
    """Test CSV import functionality."""
    from netscan_lite.importer import import_file

    csv_file = tmp_path / "test.csv"
    csv_file.write_text("ip,hostname,group\n10.0.0.1,host1,grp1\n10.0.0.2,,grp2\n")

    stats = import_file(csv_file, session)

    assert stats["imported"] == 2
    assert stats["skipped"] == 0

    # Verify IPs were created
    ips = session.exec(select(IPAddress)).all()
    assert len(ips) == 2


def test_importer_xlsx(session: Session, tmp_path):
    """Test XLSX import functionality."""
    pytest.importorskip("openpyxl")

    from openpyxl import Workbook

    from netscan_lite.importer import import_file

    xlsx_file = tmp_path / "test.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["ip", "hostname", "group"])
    ws.append(["10.0.0.1", "host1", "grp1"])
    ws.append(["10.0.0.2", "", "grp2"])
    wb.save(xlsx_file)

    stats = import_file(xlsx_file, session)

    assert stats["imported"] == 2
    assert stats["skipped"] == 0
