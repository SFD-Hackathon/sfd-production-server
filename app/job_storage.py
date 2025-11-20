"""
Job storage using R2 for persistence.

Each job is stored as a separate JSON file in R2 under jobs/ prefix.
Falls back to local file storage if R2 is not configured.
"""

import os
import json
import uuid
from typing import Dict, List, Optional
from datetime import datetime
import fcntl
from pathlib import Path
import boto3
from botocore.config import Config


# Configuration
JOBS_DIR = os.getenv("JOBS_DIR", "./jobs")
USE_R2_FOR_JOBS = os.getenv("USE_R2_FOR_JOBS", "true").lower() == "true"


class JobStorage:
    """R2-based job storage with local fallback."""

    def __init__(self, jobs_dir: str = JOBS_DIR, use_r2: bool = USE_R2_FOR_JOBS):
        """Initialize job storage.

        Args:
            jobs_dir: Directory to store job JSON files (fallback)
            use_r2: Whether to use R2 storage (default: true)
        """
        self.use_r2 = use_r2
        self.jobs_dir = Path(jobs_dir)

        # Initialize R2 client if enabled
        if self.use_r2:
            try:
                account_id = os.getenv("R2_ACCOUNT_ID")
                access_key_id = os.getenv("R2_ACCESS_KEY_ID")
                secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
                self.bucket_name = os.getenv("R2_BUCKET", "sfd-production")

                if account_id and access_key_id and secret_access_key:
                    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
                    self.s3_client = boto3.client(
                        "s3",
                        endpoint_url=endpoint_url,
                        aws_access_key_id=access_key_id,
                        aws_secret_access_key=secret_access_key,
                        config=Config(signature_version="s3v4"),
                        region_name="auto",
                    )
                    print(f"✓ Job storage initialized with R2 (bucket: {self.bucket_name})")
                else:
                    print("⚠️  R2 credentials missing, falling back to local file storage")
                    self.use_r2 = False
                    self.jobs_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"⚠️  Failed to initialize R2 for jobs: {e}, falling back to local file storage")
                self.use_r2 = False
                self.jobs_dir.mkdir(parents=True, exist_ok=True)
        else:
            print(f"✓ Job storage initialized with local files (dir: {self.jobs_dir})")
            self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _get_job_key(self, job_id: str) -> str:
        """Get R2 key for a job.

        Args:
            job_id: Job identifier

        Returns:
            R2 key for job
        """
        return f"jobs/{job_id}.json"

    def _get_job_path(self, job_id: str) -> Path:
        """Get the local file path for a job.

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
        # Save to R2 or local file
        if self.use_r2:
            try:
                key = self._get_job_key(job_id)
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=json.dumps(job, indent=2),
                    ContentType="application/json"
                )
            except Exception as e:
                print(f"Error saving job to R2: {e}, falling back to local")
                job_path = self._get_job_path(job_id)
                self._write_job_file(job_path, job)
        else:
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
        if self.use_r2:
            try:
                key = self._get_job_key(job_id)
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
                return json.loads(response["Body"].read())
            except self.s3_client.exceptions.NoSuchKey:
                return None
            except Exception as e:
                print(f"Error reading job from R2: {e}, trying local fallback")
                job_path = self._get_job_path(job_id)
                return self._read_job_file(job_path)
        else:
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
        job = self.get_job(job_id)

        if job is None:
            return None

        # Update fields
        job.update(updates)

        # Save updated job
        if self.use_r2:
            try:
                key = self._get_job_key(job_id)
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=json.dumps(job, indent=2),
                    ContentType="application/json"
                )
            except Exception as e:
                print(f"Error updating job in R2: {e}, falling back to local")
                job_path = self._get_job_path(job_id)
                self._write_job_file(job_path, job)
        else:
            job_path = self._get_job_path(job_id)
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

        if self.use_r2:
            try:
                # List all job files from R2
                paginator = self.s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=self.bucket_name, Prefix="jobs/")

                for page in pages:
                    if "Contents" not in page:
                        continue

                    for obj in page["Contents"]:
                        if not obj["Key"].endswith(".json"):
                            continue

                        try:
                            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=obj["Key"])
                            job = json.loads(response["Body"].read())

                            # Apply filters
                            if drama_id is not None and job.get("drama_id") != drama_id:
                                continue
                            if status is not None and job.get("status") != status:
                                continue

                            jobs.append(job)
                        except Exception as e:
                            print(f"Error reading job {obj['Key']}: {e}")
                            continue
            except Exception as e:
                print(f"Error listing jobs from R2: {e}, trying local fallback")
                # Fallback to local
                for job_file in self.jobs_dir.glob("*.json"):
                    job = self._read_job_file(job_file)
                    if job is None:
                        continue
                    if drama_id is not None and job.get("drama_id") != drama_id:
                        continue
                    if status is not None and job.get("status") != status:
                        continue
                    jobs.append(job)
        else:
            # Local file storage
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
