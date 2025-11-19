"""
DAG execution engine for drama generation.

Handles dependency resolution, parallel execution, and job orchestration.
"""

import os
import json
import logging
from typing import Dict, List, Set, Tuple, Optional
from pathlib import Path
from datetime import datetime
from collections import defaultdict, deque
import asyncio
import threading

from app.models import Drama, Asset
from app.job_storage import get_storage, JobStorage
from app.video_generation import generate_video_sora
from app.image_generation import generate_image
from app.asset_library import AssetLibrary
from app.config import OUTPUTS_DIR

logger = logging.getLogger(__name__)


class DAGExecutionError(Exception):
    """DAG execution error."""
    pass


class DAGExecutor:
    """Executes a drama generation DAG with dependency resolution."""

    def __init__(self, drama: Drama, user_id: str = "10000", project_name: str = None, storage: JobStorage = None):
        """Initialize DAG executor.

        Args:
            drama: Drama structure to execute
            user_id: User ID for R2 uploads (default: "10000")
            project_name: Project name for R2 uploads (defaults to drama_id)
            storage: Job storage instance (uses singleton if not provided)
        """
        self.drama = drama
        self.user_id = user_id
        self.project_name = project_name or drama.drama_id
        self.storage = storage or get_storage()
        self.dag_id = f"dag_{drama.drama_id}"
        self.parent_job_id = None  # Will be set when parent job is created

    def build_dag(self) -> Dict[str, List[str]]:
        """Build dependency graph from drama assets.

        Returns:
            Dict mapping asset_id -> list of asset_ids it depends on
        """
        dag = {}
        for asset in self.drama.get_all_assets():
            dag[asset.asset_id] = asset.depends_on or []
        return dag

    def topological_sort(self, dag: Dict[str, List[str]]) -> List[List[str]]:
        """Perform topological sort to get execution levels.

        Args:
            dag: Dependency graph

        Returns:
            List of levels, where each level is a list of asset_ids that can
            be executed in parallel

        Raises:
            DAGExecutionError: If cycle detected
        """
        # Calculate in-degree for each node
        in_degree = {node: 0 for node in dag}
        for node in dag:
            for dep in dag[node]:
                if dep in in_degree:
                    in_degree[dep] += 1

        # Find nodes with zero in-degree (no dependencies)
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        levels = []

        while queue:
            # Process all nodes at current level (can be done in parallel)
            current_level = list(queue)
            levels.append(current_level)
            queue.clear()

            # Remove current level nodes and update in-degrees
            for node in current_level:
                for dep in dag[node]:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        # Check if all nodes were processed (no cycles)
        processed_count = sum(len(level) for level in levels)
        if processed_count != len(dag):
            raise DAGExecutionError("Cycle detected in dependency graph")

        return levels

    def get_or_create_jobs(self, resume: bool = False) -> Dict[str, Dict]:
        """Get existing jobs or create new ones for all assets.

        Args:
            resume: If True, use existing jobs if available

        Returns:
            Dict mapping asset_id -> job data
        """
        assets = self.drama.get_all_assets()
        asset_ids = [asset.asset_id for asset in assets]

        # Step 1: Create or get parent job
        if not resume or not self.parent_job_id:
            # Create new parent job
            parent_job = self.storage.create_parent_job(
                drama_id=self.drama.drama_id,
                title=self.drama.title,
                user_id=self.user_id,
                project_name=self.project_name,
                metadata=self.drama.metadata or {}
            )
            self.parent_job_id = parent_job["job_id"]
            logger.info(f"Created parent job: {self.parent_job_id}")
        else:
            logger.info(f"Resuming with parent job: {self.parent_job_id}")

        # Step 2: Try to get existing child jobs
        existing_jobs = self.storage.get_jobs_by_asset_ids(asset_ids)

        # Step 3: Create or get child jobs
        jobs = {}
        child_job_ids = []

        for asset in assets:
            if resume and asset.asset_id in existing_jobs:
                # Use existing job
                job = existing_jobs[asset.asset_id]
                jobs[asset.asset_id] = job
                child_job_ids.append(job["job_id"])
            else:
                # Create new job linked to parent
                job = self.storage.create_job(
                    drama_id=self.drama.drama_id,
                    asset_id=asset.asset_id,
                    job_type=asset.type,
                    prompt=asset.prompt,
                    depends_on=asset.depends_on or [],
                    metadata={"model": self._get_model_for_asset(asset)},
                    parent_job_id=self.parent_job_id
                )
                jobs[asset.asset_id] = job
                child_job_ids.append(job["job_id"])

        # Step 4: Update parent job with child job IDs
        self.storage.update_job(self.parent_job_id, {
            "child_jobs": child_job_ids,
            "total_jobs": len(child_job_ids),
            "pending_jobs": len(child_job_ids)
        })

        return jobs

    def _get_model_for_asset(self, asset: Asset) -> str:
        """Get the model to use for an asset.

        Args:
            asset: Asset to generate

        Returns:
            Model identifier
        """
        if asset.type == "filmstrip":
            return "gemini-2.5-flash-image"
        elif asset.type == "video":
            return "sora-2"
        else:
            return "unknown"

    def execute_asset(self, asset: Asset, job: Dict, reference_paths: List[str]) -> Dict:
        """Execute generation for a single asset.

        Args:
            asset: Asset to generate
            job: Job data
            reference_paths: List of local paths to dependency outputs

        Returns:
            Updated job data

        Raises:
            Exception: If generation fails
        """
        job_id = job["job_id"]

        # Update job to running
        self.storage.update_job(job_id, {
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "reference_paths": reference_paths
        })

        # Update parent job statistics
        if self.parent_job_id:
            self.storage.update_parent_job_stats(self.parent_job_id)

        try:
            if asset.type == "filmstrip":
                # Generate image using Gemini
                result_path = self._generate_image_asset(asset, reference_paths)
            elif asset.type == "video":
                # Generate video using Sora2
                result_path = self._generate_video_asset(asset, reference_paths)
            else:
                raise DAGExecutionError(f"Unknown asset type: {asset.type}")

            # Upload to R2
            r2_url = None
            r2_key = None
            asset_metadata = None

            try:
                logger.info(f"Uploading asset {asset.asset_id} to R2...")

                # Determine asset type for R2
                if asset.type == "filmstrip":
                    r2_asset_type = "image"
                    r2_tag = "storyboard"  # Default tag for filmstrips
                elif asset.type == "video":
                    r2_asset_type = "video"
                    r2_tag = "clip"  # Default tag for videos
                else:
                    r2_asset_type = "image"
                    r2_tag = "storyboard"

                # Initialize AssetLibrary
                lib = AssetLibrary(user_id=self.user_id, project_name=self.project_name)

                # Read generated file
                with open(result_path, 'rb') as f:
                    file_content = f.read()

                # Get filename from result_path
                filename = os.path.basename(result_path)

                # Upload to R2
                asset_metadata = lib.upload_asset(
                    content=file_content,
                    asset_type=r2_asset_type,
                    tag=r2_tag,
                    filename=filename,
                    metadata={
                        'job_id': job_id,
                        'asset_id': asset.asset_id,
                        'drama_id': self.drama.drama_id,
                        'prompt': asset.prompt,
                        'model': self._get_model_for_asset(asset),
                        'source': 'ai_generation',
                        'generation_type': asset.type
                    }
                )

                r2_url = asset_metadata.get('public_url')
                r2_key = asset_metadata.get('r2_key')

                logger.info(f"✓ Uploaded asset {asset.asset_id} to R2: {r2_url}")

            except Exception as e:
                logger.error(f"Failed to upload asset {asset.asset_id} to R2: {e}")
                # Don't fail the job, just log the error
                # Asset is still available locally

            # Update job to completed
            updated_job = self.storage.update_job(job_id, {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "result_path": result_path,
                "r2_url": r2_url,
                "r2_key": r2_key,
                "asset_metadata": asset_metadata
            })

            # Update drama asset with result paths
            self.drama.update_asset(
                asset.asset_id,
                local_path=result_path,
                url=r2_url  # Set R2 URL in Asset.url field
            )

            # Update parent job statistics
            if self.parent_job_id:
                self.storage.update_parent_job_stats(self.parent_job_id)

            # Upload job metadata to R2 immediately
            self._upload_job_metadata_to_r2(updated_job)

            logger.info(f"Completed asset {asset.asset_id}: {result_path}")
            return updated_job

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to generate asset {asset.asset_id}: {error_msg}")

            # Update job to failed
            updated_job = self.storage.update_job(job_id, {
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat(),
                "error": error_msg
            })

            # Update parent job statistics
            if self.parent_job_id:
                self.storage.update_parent_job_stats(self.parent_job_id)

            return updated_job

    def _upload_job_metadata_to_r2(self, job: Dict) -> None:
        """Upload child job metadata JSON to R2.

        Args:
            job: Job data to upload
        """
        try:
            job_id = job["job_id"]
            logger.info(f"Uploading job metadata {job_id} to R2...")

            # Initialize AssetLibrary
            lib = AssetLibrary(user_id=self.user_id, project_name=self.project_name)

            # Convert job to JSON
            job_json = json.dumps(job, indent=2).encode('utf-8')

            # Upload to R2 using "text" asset type
            metadata = lib.upload_asset(
                content=job_json,
                asset_type="text",
                tag="storyboard",  # Use storyboard tag for job metadata
                filename=f"{job_id}.json",
                metadata={
                    'type': 'job_metadata',
                    'job_id': job_id,
                    'drama_id': self.drama.drama_id,
                    'asset_id': job.get('asset_id'),
                    'source': 'dag_execution'
                }
            )

            # Update job with its own R2 metadata location
            # Note: This creates a circular reference, but it's useful for tracking
            self.storage.update_job(job_id, {
                "job_metadata_r2_url": metadata.get('public_url'),
                "job_metadata_r2_key": metadata.get('r2_key')
            })

            logger.info(f"✓ Uploaded job metadata {job_id} to R2: {metadata.get('public_url')}")

        except Exception as e:
            logger.error(f"Failed to upload job metadata {job_id} to R2: {e}")
            # Don't fail the job

    def _upload_parent_job_to_r2(self, parent_job: Dict) -> None:
        """Upload parent job metadata JSON to R2.

        Args:
            parent_job: Parent job data to upload
        """
        try:
            job_id = parent_job["job_id"]
            logger.info(f"Uploading parent job metadata {job_id} to R2...")

            # Get all child jobs and enrich parent job with R2 URLs
            child_job_ids = parent_job.get("child_jobs", [])
            child_jobs_data = []

            for child_id in child_job_ids:
                child_job = self.storage.get_job(child_id)
                if child_job:
                    # Include key fields from child job
                    child_jobs_data.append({
                        "job_id": child_job["job_id"],
                        "asset_id": child_job["asset_id"],
                        "status": child_job["status"],
                        "r2_url": child_job.get("r2_url"),
                        "r2_key": child_job.get("r2_key"),
                        "job_metadata_r2_url": child_job.get("job_metadata_r2_url")
                    })

            # Enrich parent job with child job R2 URLs
            enriched_parent_job = parent_job.copy()
            enriched_parent_job["child_jobs_data"] = child_jobs_data

            # Initialize AssetLibrary
            lib = AssetLibrary(user_id=self.user_id, project_name=self.project_name)

            # Convert parent job to JSON
            parent_job_json = json.dumps(enriched_parent_job, indent=2).encode('utf-8')

            # Upload to R2 using "text" asset type
            metadata = lib.upload_asset(
                content=parent_job_json,
                asset_type="text",
                tag="episode",  # Use episode tag for parent job metadata
                filename=f"{job_id}.json",
                metadata={
                    'type': 'parent_job_metadata',
                    'job_id': job_id,
                    'drama_id': self.drama.drama_id,
                    'title': parent_job.get('title'),
                    'total_jobs': parent_job.get('total_jobs'),
                    'completed_jobs': parent_job.get('completed_jobs'),
                    'failed_jobs': parent_job.get('failed_jobs'),
                    'source': 'dag_execution'
                }
            )

            # Update parent job with its own R2 metadata location
            self.storage.update_job(job_id, {
                "r2_url": metadata.get('public_url'),
                "r2_key": metadata.get('r2_key')
            })

            logger.info(f"✓ Uploaded parent job metadata {job_id} to R2: {metadata.get('public_url')}")

        except Exception as e:
            logger.error(f"Failed to upload parent job metadata to R2: {e}")
            # Don't fail the execution

    def _generate_image_asset(self, asset: Asset, reference_paths: List[str]) -> str:
        """Generate an image asset using Gemini.

        Args:
            asset: Asset to generate
            reference_paths: Reference image paths

        Returns:
            Path to generated image
        """
        output_path = os.path.join(OUTPUTS_DIR, self.drama.drama_id, f"{asset.asset_id}.png")

        # Call the existing generate_image function from asset_api
        result = generate_image(
            prompt=asset.prompt,
            output_path=output_path,
            reference_images=reference_paths if reference_paths else None
        )

        return result["path"]

    def _generate_video_asset(self, asset: Asset, reference_paths: List[str]) -> str:
        """Generate a video asset using Sora2.

        Args:
            asset: Asset to generate
            reference_paths: Reference image paths

        Returns:
            Path to generated video
        """
        duration = asset.duration or 10

        # TODO: Convert local reference paths to URLs if needed
        # For now, Sora2 API may not support local file references
        reference_urls = []  # Skip for MVP

        result_path = generate_video_sora(
            prompt=asset.prompt,
            drama_id=self.drama.drama_id,
            asset_id=asset.asset_id,
            duration=duration,
            reference_images=reference_urls
        )

        return result_path

    def execute_level(self, level_assets: List[Asset], jobs: Dict[str, Dict]) -> List[Dict]:
        """Execute all assets in a level in parallel.

        Args:
            level_assets: List of assets to execute
            jobs: Dict of all jobs

        Returns:
            List of updated job data
        """
        results = []

        # Use threading for parallel execution
        def execute_wrapper(asset):
            try:
                # Get reference paths from dependencies
                reference_paths = []
                for dep_id in asset.depends_on or []:
                    dep_job = jobs.get(dep_id)
                    if dep_job and dep_job.get("result_path"):
                        reference_paths.append(dep_job["result_path"])

                job = jobs[asset.asset_id]
                updated_job = self.execute_asset(asset, job, reference_paths)
                results.append(updated_job)

                # Update jobs dict
                jobs[asset.asset_id] = updated_job

            except Exception as e:
                logger.error(f"Error executing asset {asset.asset_id}: {e}")
                # Job will be marked as failed in execute_asset

        threads = []
        for asset in level_assets:
            thread = threading.Thread(target=execute_wrapper, args=(asset,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        return results

    def execute_dag(self, resume: bool = False) -> DAGExecutionStatus:
        """Execute the complete DAG.

        Args:
            resume: If True, resume from existing jobs

        Returns:
            Execution status

        Raises:
            DAGExecutionError: If execution fails
        """
        logger.info(f"Starting DAG execution for drama {self.drama.drama_id}")

        # Build DAG and get execution order
        dag = self.build_dag()
        levels = self.topological_sort(dag)

        # Get or create jobs
        jobs = self.get_or_create_jobs(resume=resume)

        # Execute level by level
        for level_index, level_asset_ids in enumerate(levels):
            logger.info(f"Executing level {level_index}: {level_asset_ids}")

            # Get assets for this level
            level_assets = [
                self.drama.get_asset_by_id(asset_id)
                for asset_id in level_asset_ids
            ]

            # Skip assets that are already completed (if resuming)
            if resume:
                level_assets = [
                    asset for asset in level_assets
                    if jobs[asset.asset_id].get("status") != "completed"
                ]

            if not level_assets:
                logger.info(f"Level {level_index} already completed, skipping")
                continue

            # Execute level
            self.execute_level(level_assets, jobs)

        # Upload parent job to R2 after DAG completes
        if self.parent_job_id:
            parent_job = self.storage.get_job(self.parent_job_id)
            if parent_job:
                self._upload_parent_job_to_r2(parent_job)

        # Return final status
        return self.get_execution_status(jobs)

    def get_execution_status(self, jobs: Dict[str, Dict] = None) -> DAGExecutionStatus:
        """Get current execution status.

        Args:
            jobs: Dict of jobs (if None, will load from storage)

        Returns:
            Execution status
        """
        if jobs is None:
            # Load jobs from storage
            asset_ids = [asset.asset_id for asset in self.drama.get_all_assets()]
            jobs = self.storage.get_jobs_by_asset_ids(asset_ids)

        job_list = list(jobs.values())

        # Count statuses
        total = len(job_list)
        completed = sum(1 for j in job_list if j.get("status") == "completed")
        failed = sum(1 for j in job_list if j.get("status") == "failed")
        running = sum(1 for j in job_list if j.get("status") == "running")
        pending = sum(1 for j in job_list if j.get("status") == "pending")

        # Determine overall status
        if completed == total:
            overall_status = "completed"
        elif failed > 0 and (completed + failed) == total:
            overall_status = "failed"
        elif running > 0:
            overall_status = "running"
        else:
            overall_status = "pending"

        return DAGExecutionStatus(
            dag_id=self.dag_id,
            drama_id=self.drama.drama_id,
            status=overall_status,
            total_jobs=total,
            completed_jobs=completed,
            failed_jobs=failed,
            running_jobs=running,
            pending_jobs=pending,
            jobs=job_list
        )

    def save_drama_to_file(self) -> str:
        """Save updated drama JSON to file.

        Returns:
            Path to saved drama file
        """
        output_path = os.path.join(OUTPUTS_DIR, self.drama.drama_id, "drama.json")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(self.drama.model_dump(), f, indent=2)

        logger.info(f"Saved drama to {output_path}")
        return output_path
