"""Tests for the quarantine state machine classifier."""

from datetime import timedelta

from sqlmodel import Session

from netscan_lite.models import Group, IPAddress, IPStatus, utc_now
from netscan_lite.scanner.classifier import StateClassifier
from netscan_lite.scanner.runner import HostProbeResult, PortInfo

_group_counter = 0


def _make_group(session: Session, miss_threshold: int = 3, quarantine_hours: int = 48) -> Group:
    global _group_counter
    _group_counter += 1
    group = Group(name=f"test-{_group_counter}", miss_threshold=miss_threshold, quarantine_hours=quarantine_hours)
    session.add(group)
    session.flush()
    return group


def _make_ip(
    session: Session,
    group: Group,
    ip: str = "10.0.0.1",
    status: IPStatus = IPStatus.AVAILABLE_CANDIDATE,
    **kwargs,
) -> IPAddress:
    ip_obj = IPAddress(group_id=group.id, ip=ip, status=status, **kwargs)
    session.add(ip_obj)
    session.flush()
    return ip_obj


def _probe(up: bool = True, **kwargs) -> HostProbeResult:
    defaults = dict(
        ip="10.0.0.1",
        is_up=up,
        status_reason="syn-ack",
        discovery_method="TCP_CONNECT",
        hostname=None,
        mac_address=None,
        mac_vendor=None,
        open_ports=[],
    )
    defaults.update(kwargs)
    return HostProbeResult(**defaults)


def _probe_with_ports(up: bool = True) -> HostProbeResult:
    return _probe(
        up=up,
        hostname="web-01",
        mac_address="AA:BB:CC:DD:EE:FF",
        mac_vendor="TestVendor",
        open_ports=[PortInfo(port=443, protocol="tcp", state="open", service="https")],
    )


# --- Case 1: Reservation Lock ---


def test_reserved_ip_stays_reserved_on_up(session: Session):
    group = _make_group(session)
    ip = _make_ip(session, group, status=IPStatus.ASSIGNED_RESERVED)

    outcome = StateClassifier.classify("10.0.0.1", ip, _probe_with_ports(), group)

    assert outcome.new_status == IPStatus.ASSIGNED_RESERVED
    assert outcome.state_changed is False
    assert outcome.consecutive_misses == 0
    assert outcome.hostname == "web-01"


def test_reserved_ip_stays_reserved_on_down(session: Session):
    group = _make_group(session)
    ip = _make_ip(session, group, status=IPStatus.ASSIGNED_RESERVED, consecutive_misses=2)

    outcome = StateClassifier.classify("10.0.0.1", ip, _probe(up=False), group)

    assert outcome.new_status == IPStatus.ASSIGNED_RESERVED
    assert outcome.consecutive_misses == 3


# --- Case 2: Positive Probe ---


def test_new_ip_first_scan_becomes_active(session: Session):
    group = _make_group(session)

    outcome = StateClassifier.classify("10.0.0.1", None, _probe_with_ports(), group)

    assert outcome.new_status == IPStatus.ACTIVE_DETECTED
    assert outcome.old_status is None
    assert outcome.consecutive_misses == 0
    assert outcome.hostname == "web-01"
    assert outcome.mac_address == "AA:BB:CC:DD:EE:FF"


def test_uncertain_ip_responds_becomes_active(session: Session):
    group = _make_group(session)
    ip = _make_ip(session, group, status=IPStatus.UNCERTAIN_FIREWALLED, consecutive_misses=2)

    outcome = StateClassifier.classify("10.0.0.1", ip, _probe(), group)

    assert outcome.new_status == IPStatus.ACTIVE_DETECTED
    assert outcome.consecutive_misses == 0
    assert outcome.state_changed is True


def test_active_ip_stays_active(session: Session):
    group = _make_group(session)
    ip = _make_ip(session, group, status=IPStatus.ACTIVE_DETECTED)

    outcome = StateClassifier.classify("10.0.0.1", ip, _probe(), group)

    assert outcome.new_status == IPStatus.ACTIVE_DETECTED
    assert outcome.state_changed is False


# --- Case 3: Negative Probe ---


def test_active_ip_one_miss_stays_active(session: Session):
    group = _make_group(session, miss_threshold=3)
    ip = _make_ip(session, group, status=IPStatus.ACTIVE_DETECTED, consecutive_misses=0)

    outcome = StateClassifier.classify("10.0.0.1", ip, _probe(up=False), group)

    assert outcome.new_status == IPStatus.UNCERTAIN_FIREWALLED
    assert outcome.consecutive_misses == 1


def test_available_ip_miss_becomes_uncertain(session: Session):
    group = _make_group(session)
    ip = _make_ip(session, group, status=IPStatus.AVAILABLE_CANDIDATE)

    outcome = StateClassifier.classify("10.0.0.1", ip, _probe(up=False), group)

    # AVAILABLE + miss → falls through to default return → AVAILABLE_CANDIDATE
    assert outcome.new_status == IPStatus.AVAILABLE_CANDIDATE
    assert outcome.consecutive_misses == 1


def test_uncertain_below_threshold_stays_uncertain(session: Session):
    group = _make_group(session, miss_threshold=3, quarantine_hours=48)
    now = utc_now()
    ip = _make_ip(session, group, status=IPStatus.UNCERTAIN_FIREWALLED, consecutive_misses=1)

    outcome = StateClassifier.classify("10.0.0.1", ip, _probe(up=False), group, now=now)

    assert outcome.new_status == IPStatus.UNCERTAIN_FIREWALLED
    assert outcome.consecutive_misses == 2


def test_uncertain_meets_both_thresholds_becomes_available(session: Session):
    group = _make_group(session, miss_threshold=3, quarantine_hours=1)
    now = utc_now()
    old_time = now - timedelta(hours=2)
    ip = _make_ip(
        session,
        group,
        status=IPStatus.UNCERTAIN_FIREWALLED,
        consecutive_misses=2,
        last_seen_at=old_time,
    )

    outcome = StateClassifier.classify("10.0.0.1", ip, _probe(up=False), group, now=now)

    assert outcome.new_status == IPStatus.AVAILABLE_CANDIDATE
    assert outcome.consecutive_misses == 3


def test_uncertain_meets_misses_but_not_time_stays_uncertain(session: Session):
    group = _make_group(session, miss_threshold=2, quarantine_hours=48)
    now = utc_now()
    ip = _make_ip(
        session,
        group,
        status=IPStatus.UNCERTAIN_FIREWALLED,
        consecutive_misses=1,
        last_seen_at=now - timedelta(hours=1),
    )

    outcome = StateClassifier.classify("10.0.0.1", ip, _probe(up=False), group, now=now)

    assert outcome.new_status == IPStatus.UNCERTAIN_FIREWALLED
    assert outcome.consecutive_misses == 2


def test_uncertain_meets_time_but_not_misses_stays_uncertain(session: Session):
    group = _make_group(session, miss_threshold=5, quarantine_hours=1)
    now = utc_now()
    ip = _make_ip(
        session,
        group,
        status=IPStatus.UNCERTAIN_FIREWALLED,
        consecutive_misses=1,
        last_seen_at=now - timedelta(hours=2),
    )

    outcome = StateClassifier.classify("10.0.0.1", ip, _probe(up=False), group, now=now)

    assert outcome.new_status == IPStatus.UNCERTAIN_FIREWALLED
    assert outcome.consecutive_misses == 2


# --- Per-group thresholds ---


def test_different_groups_have_different_thresholds(session: Session):
    group_a = _make_group(session, miss_threshold=1, quarantine_hours=0)
    group_b = _make_group(session, miss_threshold=5, quarantine_hours=999)
    now = utc_now()

    ip_a = _make_ip(
        session,
        group_a,
        ip="10.0.0.1",
        status=IPStatus.UNCERTAIN_FIREWALLED,
        consecutive_misses=0,
        last_seen_at=now - timedelta(hours=1),
    )
    ip_b = _make_ip(
        session,
        group_b,
        ip="10.0.0.2",
        status=IPStatus.UNCERTAIN_FIREWALLED,
        consecutive_misses=0,
        last_seen_at=now - timedelta(hours=1),
    )

    outcome_a = StateClassifier.classify("10.0.0.1", ip_a, _probe(up=False), group_a, now=now)
    outcome_b = StateClassifier.classify("10.0.0.2", ip_b, _probe(up=False), group_b, now=now)

    assert outcome_a.new_status == IPStatus.AVAILABLE_CANDIDATE
    assert outcome_b.new_status == IPStatus.UNCERTAIN_FIREWALLED
