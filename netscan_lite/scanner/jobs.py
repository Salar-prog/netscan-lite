"""In-memory async scan job queue."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from sqlmodel import Session

from netscan_lite.db import engine

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


# ponytail: in-memory job store. Fine for single-worker; add Redis if multi-worker job tracking matters.
_jobs: Dict[str, ScanJob] = {}
MAX_CONCURRENT_JOBS = 3
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)


async def create_scan_job(
    target_ips: List[str],
    group_name: Optional[str],
    session: Session,
) -> ScanJob:
    """Create a scan job and start it in the background."""
    job_id = str(uuid.uuid4())
    job = ScanJob(job_id=job_id, target_ips=target_ips, group_name=group_name)
    _jobs[job_id] = job
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
        try:
            from netscan_lite.scanner.service import scan_ips

            with Session(engine) as session:
                result = await scan_ips(job.target_ips, session)
            job.result = result
            job.status = JobStatus.COMPLETED
            logger.info("Scan job %s completed", job.job_id)
        except Exception as e:
            job.error = str(e)
            job.status = JobStatus.FAILED
            logger.warning("Scan job %s failed: %s", job.job_id, e)
        finally:
            job.completed_at = datetime.now(timezone.utc)
