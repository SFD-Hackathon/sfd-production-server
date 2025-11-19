"""
Job storage using JSON files for persistence.

Each job is stored as a separate JSON file in the JOBS_DIR directory.
Thread-safe file operations with locking.
"""

import os
import json
import uuid
from typing import Dict, List, Optional
from datetime import datetime
import fcntl
from pathlib import Path


# Configuration
JOBS_DIR = os.getenv("JOBS_DIR", "./jobs")


class JobStorage:
    """File-based job storage with JSON persistence."""

    def __init__(self, jobs_dir: str = JOBS_DIR):
        """Initialize job storage.

        Args:
            jobs_dir: Directory to store job JSON files
        """
        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _get_job_path(self, job_id: str) -> Path:
        """Get the file path for a job.

        Args:
            job_id: Job identifier

        Returns:
            Path to job file
        """
        return self.jobs_dir / f"{job_id}.json"

    def _read_job_file(self, job_path: Path) -> Optional[Dict]:
        """Read and parse a job file with file locking.

        Args:
            job_path: Path to job file

        Returns:
            Job data as dictionary or None if file doesn't exist
        """
        if not job_path.exists():
            return None

        with open(job_path, 'r') as f:
            # Acquire shared lock for reading
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return data

    def _write_job_file(self, job_path: Path, data: Dict) -> None:
        """Write job data to file with file locking.

        Args:
            job_path: Path to job file
            data: Job data to write
        """
        # Ensure directory exists
        job_path.parent.mkdir(parents=True, exist_ok=True)

        # Write with exclusive lock
        with open(job_path, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def create_job(
        self,
        drama_id: str,
        asset_id: str,
        job_type: str,
        prompt: str,
        depends_on: List[str] = None,
        metadata: Dict = None,
        job_id: str = None,
        parent_job_id: str = None
    ) -> Dict:
        """Create a new job.

        Args:
            drama_id: Drama identifier
            asset_id: Asset identifier (e.g., "e01_s01_filmstrip")
            job_type: Type of job ("image", "video", or "filmstrip")
            prompt: Generation prompt
            depends_on: List of asset IDs this job depends on
            metadata: Additional metadata
            job_id: Optional job ID (generated if not provided)
            parent_job_id: Optional parent job ID for hierarchical jobs

        Returns:
            Created job data
        """
        if job_id is None:
            # Generate ID with asset_id prefix: job_{asset_id}_{random}
            random_suffix = uuid.uuid4().hex[:5]
            job_id = f"job_{asset_id}_{random_suffix}"

        now = datetime.utcnow().isoformat()

        job = {
            "job_id": job_id,
            "parent_job_id": parent_job_id,
            "drama_id": drama_id,
            "asset_id": asset_id,
            "type": job_type,
            "status": "pending",
            "prompt": prompt,
            "depends_on": depends_on or [],
            "reference_paths": [],
            "result_path": None,
            "r2_url": None,  # Public R2 URL for generated asset
            "r2_key": None,  # R2 key for generated asset
            "asset_metadata": None,  # Full asset metadata from AssetLibrary
            "metadata": metadata or {},
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "error": None
        }

        job_path = self._get_job_path(job_id)
        self._write_job_file(job_path, job)

        return job

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get a job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job data or None if not found
        """
        job_path = self._get_job_path(job_id)
        return self._read_job_file(job_path)

    def update_job(self, job_id: str, updates: Dict) -> Optional[Dict]:
        """Update a job.

        Args:
            job_id: Job identifier
            updates: Dictionary of fields to update

        Returns:
            Updated job data or None if job not found
        """
        job_path = self._get_job_path(job_id)
        job = self._read_job_file(job_path)

        if job is None:
            return None

        # Update fields
        job.update(updates)

        # Write back
        self._write_job_file(job_path, job)

        return job

    def list_jobs(self, drama_id: str = None, status: str = None) -> List[Dict]:
        """List all jobs, optionally filtered by drama_id and/or status.

        Args:
            drama_id: Filter by drama ID
            status: Filter by status

        Returns:
            List of job data
        """
        jobs = []

        for job_file in self.jobs_dir.glob("*.json"):
            job = self._read_job_file(job_file)
            if job is None:
                continue

            # Apply filters
            if drama_id is not None and job.get("drama_id") != drama_id:
                continue

            if status is not None and job.get("status") != status:
                continue

            jobs.append(job)

        # Sort by created_at
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return jobs

    def get_jobs_by_asset_ids(self, asset_ids: List[str]) -> Dict[str, Dict]:
        """Get jobs by asset IDs.

        Args:
            asset_ids: List of asset IDs to lookup

        Returns:
            Dictionary mapping asset_id -> job data
        """
        result = {}

        for job_file in self.jobs_dir.glob("*.json"):
            job = self._read_job_file(job_file)
            if job is None:
                continue

            asset_id = job.get("asset_id")
            if asset_id in asset_ids:
                result[asset_id] = job

        return result

    def create_parent_job(
        self,
        drama_id: str,
        title: str,
        user_id: str = "10000",
        project_name: str = None,
        child_job_ids: List[str] = None,
        metadata: Dict = None
    ) -> Dict:
        """Create a parent job for tracking overall drama execution.

        Args:
            drama_id: Drama identifier
            title: Drama title
            user_id: User ID for R2 uploads (default: "10000")
            project_name: Project name for R2 uploads (defaults to drama_id)
            child_job_ids: List of child job IDs
            metadata: Additional metadata

        Returns:
            Created parent job data
        """
        # Generate parent job ID: job_drama_{drama_short_id}_{random}
        drama_short_id = drama_id[:20] if len(drama_id) > 20 else drama_id
        random_suffix = uuid.uuid4().hex[:5]
        job_id = f"job_drama_{drama_short_id}_{random_suffix}"

        now = datetime.utcnow().isoformat()

        # Default project_name to drama_id if not provided
        if project_name is None:
            project_name = drama_id

        parent_job = {
            "job_id": job_id,
            "job_type": "drama",
            "drama_id": drama_id,
            "title": title,
            "user_id": user_id,
            "project_name": project_name,
            "status": "pending",
            "child_jobs": child_job_ids or [],
            "total_jobs": len(child_job_ids) if child_job_ids else 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "running_jobs": 0,
            "pending_jobs": len(child_job_ids) if child_job_ids else 0,
            "r2_url": None,  # R2 URL for parent job metadata JSON
            "r2_key": None,  # R2 key for parent job metadata JSON
            "metadata": metadata or {},
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "error": None
        }

        job_path = self._get_job_path(job_id)
        self._write_job_file(job_path, parent_job)

        return parent_job

    def update_parent_job_stats(self, parent_job_id: str) -> Optional[Dict]:
        """Update parent job statistics based on child job statuses.

        Args:
            parent_job_id: Parent job identifier

        Returns:
            Updated parent job or None if not found
        """
        parent_job = self.get_job(parent_job_id)
        if not parent_job:
            return None

        # Get all child jobs
        child_job_ids = parent_job.get("child_jobs", [])
        child_jobs = [self.get_job(cid) for cid in child_job_ids]
        child_jobs = [j for j in child_jobs if j is not None]

        # Count statuses
        total = len(child_jobs)
        completed = sum(1 for j in child_jobs if j.get("status") == "completed")
        failed = sum(1 for j in child_jobs if j.get("status") == "failed")
        running = sum(1 for j in child_jobs if j.get("status") == "running")
        pending = sum(1 for j in child_jobs if j.get("status") == "pending")

        # Determine overall status
        if completed == total and total > 0:
            overall_status = "completed"
        elif failed > 0 and (completed + failed) == total:
            overall_status = "failed"
        elif running > 0:
            overall_status = "running"
        else:
            overall_status = "pending"

        # Update parent job
        updates = {
            "status": overall_status,
            "total_jobs": total,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "running_jobs": running,
            "pending_jobs": pending
        }

        # Set started_at if not set and status is running
        if overall_status == "running" and not parent_job.get("started_at"):
            updates["started_at"] = datetime.utcnow().isoformat()

        # Set completed_at if completed or failed
        if overall_status in ["completed", "failed"] and not parent_job.get("completed_at"):
            updates["completed_at"] = datetime.utcnow().isoformat()

        return self.update_job(parent_job_id, updates)

    def get_child_jobs(self, parent_job_id: str) -> List[Dict]:
        """Get all child jobs for a parent job.

        Args:
            parent_job_id: Parent job identifier

        Returns:
            List of child job data
        """
        parent_job = self.get_job(parent_job_id)
        if not parent_job:
            return []

        child_job_ids = parent_job.get("child_jobs", [])
        child_jobs = []

        for child_id in child_job_ids:
            child_job = self.get_job(child_id)
            if child_job:
                child_jobs.append(child_job)

        return child_jobs

    def delete_job(self, job_id: str) -> bool:
        """Delete a job.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted, False if not found
        """
        job_path = self._get_job_path(job_id)

        if not job_path.exists():
            return False

        job_path.unlink()
        return True


# Singleton instance
_storage = None


def get_storage() -> JobStorage:
    """Get the singleton job storage instance."""
    global _storage
    if _storage is None:
        _storage = JobStorage()
    return _storage
