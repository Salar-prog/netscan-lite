"""Tests for CSV/XLSX importer edge cases."""
import pytest
from sqlmodel import Session, select

from netscan_lite.importer import import_file
from netscan_lite.models import Group, IPAddress


def test_import_invalid_ip_skipped(session: Session, tmp_path):
    csv = tmp_path / "bad.csv"
    csv.write_text("ip,hostname\nnot-an-ip,host1\n10.0.0.1,host2\n")

    stats = import_file(csv, session)

    assert stats["imported"] == 1
    assert stats["skipped"] == 1
    assert any("invalid IP" in e for e in stats["errors"])


def test_import_missing_ip_column_skipped(session: Session, tmp_path):
    csv = tmp_path / "noip.csv"
    csv.write_text("hostname,group\nweb-01,infra\n")

    stats = import_file(csv, session)

    assert stats["imported"] == 0
    assert stats["skipped"] == 1
    assert any("missing IP" in e for e in stats["errors"])


def test_import_duplicate_ip_skipped(session: Session, tmp_path):
    csv = tmp_path / "dup.csv"
    csv.write_text("ip,group\n10.0.0.1,infra\n10.0.0.1,infra\n")

    stats = import_file(csv, session)

    assert stats["imported"] == 1
    assert stats["skipped"] == 1


def test_import_same_ip_different_groups(session: Session, tmp_path):
    csv = tmp_path / "multi.csv"
    csv.write_text("ip,group\n10.0.0.1,group-a\n10.0.0.1,group-b\n")

    stats = import_file(csv, session)

    assert stats["imported"] == 2
    ips = session.exec(select(IPAddress)).all()
    assert len(ips) == 2


def test_import_empty_file(session: Session, tmp_path):
    csv = tmp_path / "empty.csv"
    csv.write_text("ip,hostname,group\n")

    stats = import_file(csv, session)

    assert stats["imported"] == 0
    assert stats["skipped"] == 0


def test_import_group_override(session: Session, tmp_path):
    csv = tmp_path / "override.csv"
    csv.write_text("ip,group\n10.0.0.1,original\n10.0.0.2,original\n")

    stats = import_file(csv, session, group_name="overridden")

    assert stats["imported"] == 2
    groups = session.exec(select(Group)).all()
    assert len(groups) == 1
    assert groups[0].name == "overridden"


def test_import_creates_group_with_defaults(session: Session, tmp_path):
    csv = tmp_path / "newgrp.csv"
    csv.write_text("ip,group\n10.0.0.1,new-group\n")

    import_file(csv, session)

    group = session.exec(select(Group).where(Group.name == "new-group")).first()
    assert group is not None
    assert group.miss_threshold == 3
    assert group.quarantine_hours == 48


def test_import_reuses_existing_group(session: Session, tmp_path):
    existing = Group(name="infra", miss_threshold=5, quarantine_hours=12)
    session.add(existing)
    session.commit()

    csv = tmp_path / "reuse.csv"
    csv.write_text("ip,group\n10.0.0.1,infra\n")

    import_file(csv, session)

    groups = session.exec(select(Group).where(Group.name == "infra")).all()
    assert len(groups) == 1
    assert groups[0].miss_threshold == 5


def test_import_unsupported_format(session: Session, tmp_path):
    bad = tmp_path / "data.json"
    bad.write_text("{}")

    with pytest.raises(ValueError, match="Unsupported"):
        import_file(bad, session)


def test_import_hostname_optional(session: Session, tmp_path):
    csv = tmp_path / "nohost.csv"
    csv.write_text("ip\n10.0.0.1\n")

    stats = import_file(csv, session)

    assert stats["imported"] == 1
    ip = session.exec(select(IPAddress)).first()
    assert ip.hostname is None
