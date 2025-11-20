"""
Job Repository

Data access layer for job-related operations with hierarchical DAG support.
"""

import logging
from typing import Dict, List, Optional
from supabase import Client
from datetime import datetime
from app.dal.base import BaseRepository

logger = logging.getLogger(__name__)


class JobRepository(BaseRepository):
    """Repository for job table operations"""

    def __init__(self, client: Client):
        super().__init__(client, "jobs")

    async def create_job(
        self,
        user_id: str,
        drama_id: str,
        job_id: str,
        job_type: str,
        asset_id: Optional[str] = None,
        parent_job_id: Optional[str] = None,
        prompt: Optional[str] = None,
        status: str = "pending",
        total_jobs: int = 1,
    ) -> Optional[Dict]:
        """
        Create a new job with hierarchical DAG support.

        Args:
            user_id: User who owns the job
            drama_id: Associated drama ID
            job_id: External job ID
            job_type: Type of job (generate_drama, generate_image, etc.)
            asset_id: Optional asset ID this job is generating
            parent_job_id: Optional parent job ID for hierarchical tracking
            prompt: Optional prompt for generation
            status: Job status (default: pending)
            total_jobs: Total child jobs (for parent jobs)

        Returns:
            Created job record or None if failed
        """
        job_data = {
            "user_id": user_id,
            "drama_id": drama_id,
            "job_id": job_id,
            "job_type": job_type,
            "status": status,
            "total_jobs": total_jobs,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "running_jobs": 0,
        }

        if asset_id:
            job_data["asset_id"] = asset_id
        if parent_job_id:
            job_data["parent_job_id"] = parent_job_id
        if prompt:
            job_data["prompt"] = prompt

        return await self.create(job_data)

    async def get_job_by_job_id(self, job_id: str) -> Optional[Dict]:
        """Get job by external job_id"""
        return await self.find_by_id("job_id", job_id)

    async def get_job_by_drama_id(self, drama_id: str) -> Optional[Dict]:
        """Get job by drama_id (returns first match)"""
        jobs = await self.find_all(filters={"drama_id": drama_id}, limit=1)
        return jobs[0] if jobs else None

    async def get_user_jobs(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get all jobs for a user, optionally filtered by status.

        Args:
            user_id: User ID
            status: Optional status filter
            limit: Maximum results (default: 100)

        Returns:
            List of job records
        """
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status

        return await self.find_all(
            filters=filters,
            limit=limit,
            order_by="created_at",
            ascending=False
        )

    async def get_active_jobs(self, user_id: str) -> List[Dict]:
        """Get all pending/processing jobs for a user"""
        try:
            response = (
                self.table.select("*")
                .eq("user_id", user_id)
                .in_("status", ["pending", "processing"])
                .order("created_at", desc=True)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error getting active jobs for user {user_id}: {e}")
            return []

    async def get_active_drama_jobs(self, drama_id: str) -> List[Dict]:
        """Get all active jobs for a specific drama"""
        try:
            response = (
                self.table.select("*")
                .eq("drama_id", drama_id)
                .in_("status", ["pending", "processing"])
                .order("created_at", desc=True)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error getting active drama jobs for {drama_id}: {e}")
            return []

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        error: Optional[str] = None,
        r2_url: Optional[str] = None,
        completed_jobs: Optional[int] = None,
        failed_jobs: Optional[int] = None,
        running_jobs: Optional[int] = None,
    ) -> Optional[Dict]:
        """
        Update job status and related fields.

        Args:
            job_id: External job ID
            status: New status
            error: Optional error message
            r2_url: Optional R2 result URL
            completed_jobs: Optional completed jobs count
            failed_jobs: Optional failed jobs count
            running_jobs: Optional running jobs count

        Returns:
            Updated job record or None if failed
        """
        update_data = {"status": status}

        if error:
            update_data["error"] = error
        if r2_url:
            update_data["r2_url"] = r2_url
        if completed_jobs is not None:
            update_data["completed_jobs"] = completed_jobs
        if failed_jobs is not None:
            update_data["failed_jobs"] = failed_jobs
        if running_jobs is not None:
            update_data["running_jobs"] = running_jobs

        # Add timestamps based on status
        if status == "processing":
            update_data["started_at"] = datetime.utcnow().isoformat()
        elif status in ["completed", "failed"]:
            update_data["completed_at"] = datetime.utcnow().isoformat()

        return await self.update("job_id", job_id, update_data)

    # ==========================================================================
    # Hierarchical DAG Support
    # ==========================================================================

    async def get_child_jobs(self, parent_job_id: str) -> List[Dict]:
        """
        Get all child jobs for a parent job.

        Args:
            parent_job_id: External job ID of parent

        Returns:
            List of child job records
        """
        try:
            response = (
                self.table.select("*")
                .eq("parent_job_id", parent_job_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error getting child jobs for {parent_job_id}: {e}")
            return []

    async def get_parent_job(self, child_job_id: str) -> Optional[Dict]:
        """Get parent job for a child job"""
        child_job = await self.get_job_by_job_id(child_job_id)
        if not child_job or not child_job.get("parent_job_id"):
            return None

        return await self.get_job_by_job_id(child_job["parent_job_id"])

    async def get_job_hierarchy(self, job_id: str) -> Dict:
        """
        Get complete job hierarchy (parent + all children).

        Args:
            job_id: External job ID (parent)

        Returns:
            Dict with 'parent' and 'children' keys
        """
        parent = await self.get_job_by_job_id(job_id)
        if not parent:
            return {"parent": None, "children": []}

        children = await self.get_child_jobs(job_id)

        return {
            "parent": parent,
            "children": children
        }

    async def update_parent_job_progress(self, parent_job_id: str) -> bool:
        """
        Recalculate and update parent job progress based on children.

        Args:
            parent_job_id: External job ID of parent

        Returns:
            True if successful, False otherwise
        """
        try:
            children = await self.get_child_jobs(parent_job_id)

            total_jobs = len(children)
            completed_jobs = sum(1 for j in children if j["status"] == "completed")
            failed_jobs = sum(1 for j in children if j["status"] == "failed")
            running_jobs = sum(1 for j in children if j["status"] == "processing")

            # Update parent job counters
            await self.update("job_id", parent_job_id, {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "running_jobs": running_jobs,
            })

            # Determine parent status
            if completed_jobs == total_jobs:
                parent_status = "completed"
            elif failed_jobs > 0 and (completed_jobs + failed_jobs == total_jobs):
                parent_status = "failed"  # All done but some failed
            else:
                parent_status = "processing"

            await self.update_job_status(parent_job_id, parent_status)

            return True
        except Exception as e:
            logger.error(f"Error updating parent job progress for {parent_job_id}: {e}")
            return False

    async def get_jobs_by_asset_id(self, asset_id: str) -> List[Dict]:
        """
        Get all jobs related to a specific asset.

        Args:
            asset_id: Asset ID (character_id, episode_id, etc.)

        Returns:
            List of job records
        """
        return await self.find_all(
            filters={"asset_id": asset_id},
            order_by="created_at",
            ascending=False
        )

    async def get_jobs_by_asset_ids(self, asset_ids: List[str]) -> Dict[str, Dict]:
        """
        Get jobs by multiple asset IDs.

        Args:
            asset_ids: List of asset IDs to lookup

        Returns:
            Dictionary mapping asset_id -> job data (first match)
        """
        try:
            if not asset_ids:
                return {}

            response = (
                self.table.select("*")
                .in_("asset_id", asset_ids)
                .order("created_at", desc=True)
                .execute()
            )

            # Create mapping: asset_id -> first job
            result = {}
            for job in response.data:
                asset_id = job.get("asset_id")
                if asset_id and asset_id not in result:
                    result[asset_id] = job

            return result
        except Exception as e:
            logger.error(f"Error getting jobs by asset IDs: {e}")
            return {}

    async def delete_drama_jobs(self, drama_id: str) -> bool:
        """
        Delete all jobs for a specific drama.

        Args:
            drama_id: Drama ID

        Returns:
            True if successful, False otherwise
        """
        try:
            self.table.delete().eq("drama_id", drama_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting jobs for drama {drama_id}: {e}")
            return False
