"""In-memory async scan job queue with cleanup."""

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional

from sqlmodel import Session

from netscan_lite.db import engine
from netscan_lite.logging_config import audit

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanJob:
    __slots__ = (
        "job_id",
        "target_ips",
        "group_name",
        "status",
        "result",
        "error",
        "created_at",
        "started_at",
        "completed_at",
    )

    def __init__(self, job_id: str, target_ips: List[str], group_name: Optional[str]):
        self.job_id = job_id
        self.target_ips = target_ips
        self.group_name = group_name
        self.status = JobStatus.PENDING
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None


_jobs: Dict[str, ScanJob] = {}
MAX_CONCURRENT_JOBS = 3
MAX_JOBS = 50
JOB_TTL_HOURS = 24
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
_cleanup_event = threading.Event()


def _cleanup_expired_jobs() -> None:
    """Remove completed/failed jobs older than TTL, enforce max cap."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=JOB_TTL_HOURS)

    expired = [
        jid for jid, j in _jobs.items() if j.status in (JobStatus.COMPLETED, JobStatus.FAILED) and j.created_at < cutoff
    ]
    for jid in expired:
        del _jobs[jid]
    if expired:
        logger.info("Cleaned up %d expired scan jobs", len(expired))

    # Enforce max cap: drop oldest completed first
    completed = sorted(
        [(jid, j) for jid, j in _jobs.items() if j.status in (JobStatus.COMPLETED, JobStatus.FAILED)],
        key=lambda x: x[1].created_at,
    )
    while len(_jobs) > MAX_JOBS and completed:
        jid, _ = completed.pop(0)
        del _jobs[jid]
        logger.info("Evicted scan job %s (max cap)", jid)


def _cleanup_loop() -> None:
    """Periodic job cleanup (sync, runs in background thread)."""
    while not _cleanup_event.is_set():
        try:
            _cleanup_expired_jobs()
        except Exception as e:
            logger.warning("Job cleanup error: %s", e)
        _cleanup_event.wait(3600)


def stop_cleanup_task() -> None:
    """Signal the cleanup loop to stop immediately."""
    _cleanup_event.set()


def start_cleanup_task():
    """Start the background job cleanup loop. Returns an awaitable handle, or None in tests."""
    _cleanup_event.clear()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return loop.run_in_executor(None, _cleanup_loop)


async def create_scan_job(
    target_ips: List[str],
    group_name: Optional[str],
    session: Session,
) -> ScanJob:
    """Create a scan job and start it in the background."""
    job_id = str(uuid.uuid4())
    job = ScanJob(job_id=job_id, target_ips=target_ips, group_name=group_name)
    _jobs[job_id] = job
    audit("scan_job_create", detail=f"job_id={job_id} targets={len(target_ips)} group={group_name or 'all'}")
    asyncio.create_task(_run_job(job))
    return job


def get_job(job_id: str) -> Optional[ScanJob]:
    """Get a scan job by ID."""
    return _jobs.get(job_id)


def list_jobs() -> List[ScanJob]:
    """List all scan jobs."""
    return list(_jobs.values())


async def _run_job(job: ScanJob) -> None:
    """Execute the scan job."""
    async with _semaphore:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        logger.info("Scan job %s started (%d targets)", job.job_id, len(job.target_ips))
        audit("scan_job_start", detail=f"job_id={job.job_id} targets={len(job.target_ips)}")
        try:
            from netscan_lite.scanner.service import scan_ips

            with Session(engine) as session:
                result = await scan_ips(job.target_ips, session)
            job.result = result
            job.status = JobStatus.COMPLETED
            logger.info("Scan job %s completed", job.job_id)
            audit(
                "scan_job_complete",
                detail=f"job_id={job.job_id} scanned={result['scanned']} active={result['active']} "
                f"uncertain={result['uncertain']} available={result['available']}",
            )
        except Exception as e:
            job.error = str(e)
            job.status = JobStatus.FAILED
            logger.warning("Scan job %s failed: %s", job.job_id, e)
            audit("scan_job_failed", result="error", detail=f"job_id={job.job_id} error={e}")
        finally:
            job.completed_at = datetime.now(timezone.utc)
