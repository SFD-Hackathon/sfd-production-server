"""Job management for async drama generation"""

import time
from typing import Dict, Optional
from app.models import JobStatusRecord, JobType, JobStatus


class JobManager:
    """In-memory job status manager"""

    def __init__(self):
        """Initialize job manager"""
        self.jobs: Dict[str, JobStatusRecord] = {}

    def create_job(self, job_id: str, drama_id: str, job_type: JobType) -> JobStatusRecord:
        """
        Create a new job

        Args:
            job_id: Unique job ID
            drama_id: Associated drama ID
            job_type: Type of job

        Returns:
            Created job record
        """
        job = JobStatusRecord(
            jobId=job_id,
            type=job_type,
            status=JobStatus.pending,
            dramaId=drama_id,
            createdAt=int(time.time() * 1000),
            startedAt=None,
            completedAt=None,
            error=None,
            result=None,
        )
        self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[JobStatusRecord]:
        """
        Get job by ID

        Args:
            job_id: Job ID to retrieve

        Returns:
            Job record if found, None otherwise
        """
        return self.jobs.get(job_id)

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None,
        result: Optional[Dict] = None,
    ) -> Optional[JobStatusRecord]:
        """
        Update job status

        Args:
            job_id: Job ID to update
            status: New status
            error: Error message if failed
            result: Result data if completed

        Returns:
            Updated job record if found, None otherwise
        """
        job = self.jobs.get(job_id)
        if not job:
            return None

        job.status = status

        if status == JobStatus.processing and job.startedAt is None:
            job.startedAt = int(time.time() * 1000)

        if status in [JobStatus.completed, JobStatus.failed]:
            job.completedAt = int(time.time() * 1000)

        if error:
            job.error = error

        if result:
            job.result = result

        return job

    def get_drama_jobs(self, drama_id: str) -> list[JobStatusRecord]:
        """
        Get all jobs for a drama

        Args:
            drama_id: Drama ID

        Returns:
            List of job records
        """
        return [job for job in self.jobs.values() if job.dramaId == drama_id]


# Global job manager instance
job_manager = JobManager()
