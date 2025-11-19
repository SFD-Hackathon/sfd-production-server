"""
Improved DAG execution engine for drama generation with hierarchical architecture.

Hierarchical Architecture:
- Root: drama
- h=1: character, episode
- h=2: character_asset, scenes
- h=3: scene_assets

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

try:
    from app.models import Drama, Character, Episode, Scene, Asset, AssetKind
    from app.job_storage import get_storage, JobStorage
    from app.video_generation import generate_video_sora
    from app.image_generation import generate_image
    from app.asset_library import AssetLibrary
    from app.config import OUTPUTS_DIR
except ImportError:
    # Fallback for standalone execution
    from models import Drama, Character, Episode, Scene, Asset, AssetKind
    from job_storage import get_storage, JobStorage
    from video_generation import generate_video_sora
    from image_generation import generate_image
    from asset_library import AssetLibrary
    from config import OUTPUTS_DIR

logger = logging.getLogger(__name__)


# Valid node types in hierarchical DAG
class NodeType:
    """Node types for hierarchical drama generation DAG."""
    CHARACTER = "character"           # h=1: Character portrait
    EPISODE = "episode"               # h=1: Episode (placeholder)
    CHARACTER_ASSET = "character_asset"  # h=2: Character asset (video/image)
    SCENE = "scene"                   # h=2: Scene storyboard
    SCENE_ASSET = "scene_asset"       # h=3: Scene asset (video/image clip)

    # Branch groupings
    CHARACTER_BRANCH = {CHARACTER, CHARACTER_ASSET}
    EPISODE_BRANCH = {EPISODE, SCENE, SCENE_ASSET}
    ALL = {CHARACTER, EPISODE, CHARACTER_ASSET, SCENE, SCENE_ASSET}


class DAGExecutionError(Exception):
    """DAG execution error."""
    pass


class DAGNode:
    """Represents a node in the generation DAG."""

    def __init__(
        self,
        node_id: str,
        node_type: str,  # "character", "character_asset", "episode", "scene", "scene_asset"
        hierarchy_level: int,  # 0=root, 1=character/episode, 2=character_asset/scene, 3=scene_asset
        entity_id: str,  # ID of the actual entity (character_id, scene_id, asset_id, etc.)
        parent_id: Optional[str] = None,
        prompt: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.node_id = node_id
        self.node_type = node_type
        self.hierarchy_level = hierarchy_level
        self.entity_id = entity_id
        self.parent_id = parent_id
        self.prompt = prompt
        self.metadata = metadata or {}
        self.dependencies = []  # List of node_ids this depends on

    def __repr__(self):
        return f"DAGNode(id={self.node_id}, type={self.node_type}, level={self.hierarchy_level})"


class HierarchicalDAGExecutor:
    """Executes drama generation DAG based on hierarchical architecture."""

    def __init__(
        self,
        drama: Drama,
        user_id: str = "10000",
        project_name: str = None,
        storage: JobStorage = None
    ):
        """Initialize hierarchical DAG executor.

        Args:
            drama: Drama model instance
            user_id: User ID for R2 uploads (default: "10000")
            project_name: Project name for R2 uploads (defaults to drama_id)
            storage: Job storage instance (uses singleton if not provided)
        """
        self.drama = drama
        self.user_id = user_id
        self.project_name = project_name or drama.id
        self.storage = storage or get_storage()
        self.dag_id = f"dag_{drama.id}"
        self.parent_job_id = None
        self.nodes = {}  # Map node_id -> DAGNode
        self.jobs = {}   # Map node_id -> job data

    def build_hierarchical_dag(self) -> Dict[str, List[str]]:
        """Build dependency graph from drama hierarchical structure.

        Hierarchy:
        - h=1: characters, episodes
        - h=2: character assets (depend on characters), scenes (depend on episodes)
        - h=3: scene assets (depend on scenes)

        Returns:
            Dict mapping node_id -> list of node_ids it depends on
        """
        self.nodes = {}
        dag = {}

        # Level 1: Characters and Episodes
        for character in self.drama.characters:
            node_id = f"char_{character.id}"
            node = DAGNode(
                node_id=node_id,
                node_type="character",
                hierarchy_level=1,
                entity_id=character.id,
                prompt=character.description,
                metadata={"name": character.name, "gender": character.gender}
            )
            self.nodes[node_id] = node
            dag[node_id] = []  # No dependencies at level 1

        for episode in self.drama.episodes:
            node_id = f"ep_{episode.id}"
            node = DAGNode(
                node_id=node_id,
                node_type="episode",
                hierarchy_level=1,
                entity_id=episode.id,
                prompt=episode.description,
                metadata={"title": episode.title}
            )
            self.nodes[node_id] = node
            dag[node_id] = []  # No dependencies at level 1

        # Level 2: Character Assets and Scenes
        for character in self.drama.characters:
            char_node_id = f"char_{character.id}"

            for asset in character.assets:
                asset_node_id = f"char_asset_{character.id}_{asset.id}"
                node = DAGNode(
                    node_id=asset_node_id,
                    node_type="character_asset",
                    hierarchy_level=2,
                    entity_id=asset.id,
                    parent_id=char_node_id,
                    prompt=asset.prompt,
                    metadata={
                        "character_id": character.id,
                        "asset_kind": asset.kind,
                        "depends_on": asset.depends_on
                    }
                )
                self.nodes[asset_node_id] = node
                # Character assets depend on their parent character
                dag[asset_node_id] = [char_node_id]

        for episode in self.drama.episodes:
            ep_node_id = f"ep_{episode.id}"

            for scene in episode.scenes:
                scene_node_id = f"scene_{episode.id}_{scene.id}"
                node = DAGNode(
                    node_id=scene_node_id,
                    node_type="scene",
                    hierarchy_level=2,
                    entity_id=scene.id,
                    parent_id=ep_node_id,
                    prompt=scene.description,
                    metadata={"episode_id": episode.id}
                )
                self.nodes[scene_node_id] = node
                # Scenes depend on their parent episode
                dag[scene_node_id] = [ep_node_id]

        # Level 3: Scene Assets
        for episode in self.drama.episodes:
            for scene in episode.scenes:
                scene_node_id = f"scene_{episode.id}_{scene.id}"

                for asset in scene.assets:
                    asset_node_id = f"scene_asset_{episode.id}_{scene.id}_{asset.id}"

                    # Determine dependencies
                    dependencies = [scene_node_id]  # Always depend on parent scene

                    # Add character dependencies if specified in asset.depends_on
                    if asset.depends_on:
                        for dep_id in asset.depends_on:
                            # Check if it's a character ID
                            if any(c.id == dep_id for c in self.drama.characters):
                                char_node_id = f"char_{dep_id}"
                                if char_node_id in dag:
                                    dependencies.append(char_node_id)
                            # Check if it's another scene asset ID in the same scene
                            else:
                                dep_asset_node_id = f"scene_asset_{episode.id}_{scene.id}_{dep_id}"
                                if dep_asset_node_id in self.nodes:
                                    dependencies.append(dep_asset_node_id)

                    node = DAGNode(
                        node_id=asset_node_id,
                        node_type="scene_asset",
                        hierarchy_level=3,
                        entity_id=asset.id,
                        parent_id=scene_node_id,
                        prompt=asset.prompt,
                        metadata={
                            "episode_id": episode.id,
                            "scene_id": scene.id,
                            "asset_kind": asset.kind,
                            "duration": asset.duration,
                            "depends_on": asset.depends_on
                        }
                    )
                    self.nodes[asset_node_id] = node
                    dag[asset_node_id] = dependencies

        return dag

    def topological_sort(self, dag: Dict[str, List[str]]) -> List[List[str]]:
        """Perform topological sort to get execution levels.

        Args:
            dag: Dependency graph

        Returns:
            List of levels, where each level is a list of node_ids that can
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
        """Get existing jobs or create new ones for all nodes.

        Args:
            resume: If True, use existing jobs if available

        Returns:
            Dict mapping node_id -> job data
        """
        # Create parent job if needed
        if not resume or not self.parent_job_id:
            parent_job = self.storage.create_parent_job(
                drama_id=self.drama.id,
                title=self.drama.title,
                user_id=self.user_id,
                project_name=self.project_name,
                metadata=self.drama.metadata or {}
            )
            self.parent_job_id = parent_job["job_id"]
            logger.info(f"Created parent job: {self.parent_job_id}")
        else:
            logger.info(f"Resuming with parent job: {self.parent_job_id}")

        # Get existing jobs by entity IDs
        entity_ids = [node.entity_id for node in self.nodes.values()]
        existing_jobs_by_asset_id = self.storage.get_jobs_by_asset_ids(entity_ids)

        # Create or get jobs for each node
        jobs = {}
        child_job_ids = []

        for node_id, node in self.nodes.items():
            if resume and node.entity_id in existing_jobs_by_asset_id:
                # Use existing job
                job = existing_jobs_by_asset_id[node.entity_id]
                jobs[node_id] = job
                child_job_ids.append(job["job_id"])
            else:
                # Determine job type based on node type
                if node.node_type in ["character", "character_asset", "scene"]:
                    job_type = "image"
                elif node.node_type == "scene_asset":
                    # Check if it's image or video
                    asset_kind = node.metadata.get("asset_kind")
                    if asset_kind == "video" or asset_kind == AssetKind.video:
                        job_type = "video"
                    else:
                        job_type = "image"
                elif node.node_type == "episode":
                    job_type = "episode"  # Episode generation (placeholder)
                else:
                    job_type = "unknown"

                # Create new job
                job = self.storage.create_job(
                    drama_id=self.drama.id,
                    asset_id=node.entity_id,
                    job_type=job_type,
                    prompt=node.prompt or "",
                    depends_on=[self.nodes[dep_id].entity_id for dep_id in node.dependencies if dep_id in self.nodes],
                    metadata={
                        "node_id": node_id,
                        "node_type": node.node_type,
                        "hierarchy_level": node.hierarchy_level,
                        **node.metadata
                    },
                    parent_job_id=self.parent_job_id
                )
                jobs[node_id] = job
                child_job_ids.append(job["job_id"])

        # Update parent job with child job IDs
        self.storage.update_job(self.parent_job_id, {
            "child_jobs": child_job_ids,
            "total_jobs": len(child_job_ids),
            "pending_jobs": len(child_job_ids)
        })

        self.jobs = jobs
        return jobs

    def execute_node(self, node: DAGNode, job: Dict, dependency_results: Dict[str, Dict]) -> Dict:
        """Execute generation for a single node.

        Args:
            node: DAG node to execute
            job: Job data
            dependency_results: Dict mapping dependency node_id -> job result

        Returns:
            Updated job data
        """
        job_id = job["job_id"]

        # Update job to running
        self.storage.update_job(job_id, {
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        })

        # Update parent job statistics
        if self.parent_job_id:
            self.storage.update_parent_job_stats(self.parent_job_id)

        try:
            result_path = None
            r2_url = None
            r2_key = None
            asset_metadata = None

            # Execute based on node type
            if node.node_type == "character":
                result_path, r2_url, r2_key, asset_metadata = self._generate_character(node)
            elif node.node_type == "character_asset":
                result_path, r2_url, r2_key, asset_metadata = self._generate_character_asset(node, dependency_results)
            elif node.node_type == "episode":
                # Episode doesn't generate assets, just a placeholder
                result_path = None
            elif node.node_type == "scene":
                result_path, r2_url, r2_key, asset_metadata = self._generate_scene(node, dependency_results)
            elif node.node_type == "scene_asset":
                result_path, r2_url, r2_key, asset_metadata = self._generate_scene_asset(node, dependency_results)
            else:
                raise DAGExecutionError(f"Unknown node type: {node.node_type}")

            # Update job to completed
            updated_job = self.storage.update_job(job_id, {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "result_path": result_path,
                "r2_url": r2_url,
                "r2_key": r2_key,
                "asset_metadata": asset_metadata
            })

            # Update drama model with results
            self._update_drama_model(node, result_path, r2_url)

            # Update parent job statistics
            if self.parent_job_id:
                self.storage.update_parent_job_stats(self.parent_job_id)

            logger.info(f"Completed node {node.node_id}: {result_path}")
            return updated_job

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to generate node {node.node_id}: {error_msg}")

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

    def _generate_character(self, node: DAGNode) -> Tuple[str, str, str, Dict]:
        """Generate character image.

        Returns:
            (result_path, r2_url, r2_key, asset_metadata)
        """
        output_path = os.path.join(OUTPUTS_DIR, self.drama.id, "characters", f"{node.entity_id}.png")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Generate image
        result = generate_image(
            prompt=node.prompt,
            output_path=output_path
        )

        # Upload to R2
        r2_url, r2_key, asset_metadata = self._upload_to_r2(
            file_path=result["path"],
            asset_type="image",
            tag="character",
            metadata={
                "character_id": node.entity_id,
                "name": node.metadata.get("name"),
                "type": "character_portrait"
            }
        )

        # Log generation success with paths
        character_name = node.metadata.get("name", node.entity_id)
        print(f"✓ Character image generation completed for {character_name}. local_path: {result['path']}, public_url: {r2_url}")

        return result["path"], r2_url, r2_key, asset_metadata

    def _generate_character_asset(self, node: DAGNode, dependency_results: Dict) -> Tuple[str, str, str, Dict]:
        """Generate character asset (image or video).

        Returns:
            (result_path, r2_url, r2_key, asset_metadata)
        """
        asset_kind = node.metadata.get("asset_kind")
        character_id = node.metadata.get("character_id")

        if asset_kind == "video" or asset_kind == AssetKind.video:
            # Generate video
            output_path = os.path.join(OUTPUTS_DIR, self.drama.id, "characters", f"{node.entity_id}.mp4")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            result_path = generate_video_sora(
                prompt=node.prompt,
                drama_id=self.drama.id,
                asset_id=node.entity_id,
                duration=10
            )

            r2_url, r2_key, asset_metadata = self._upload_to_r2(
                file_path=result_path,
                asset_type="video",
                tag="character",
                metadata={
                    "character_id": character_id,
                    "type": "character_video"
                }
            )

            # Log generation success with paths
            print(f"✓ Character video asset generation completed for {character_id}/{node.entity_id}. local_path: {result_path}, public_url: {r2_url}")
        else:
            # Generate image
            output_path = os.path.join(OUTPUTS_DIR, self.drama.id, "characters", f"{node.entity_id}.png")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            result = generate_image(
                prompt=node.prompt,
                output_path=output_path
            )

            r2_url, r2_key, asset_metadata = self._upload_to_r2(
                file_path=result["path"],
                asset_type="image",
                tag="character",
                metadata={
                    "character_id": character_id,
                    "type": "character_asset"
                }
            )
            result_path = result["path"]

            # Log generation success with paths
            print(f"✓ Character image asset generation completed for {character_id}/{node.entity_id}. local_path: {result_path}, public_url: {r2_url}")

        return result_path, r2_url, r2_key, asset_metadata

    def _generate_scene(self, node: DAGNode, dependency_results: Dict) -> Tuple[str, str, str, Dict]:
        """Generate scene image (storyboard).

        Returns:
            (result_path, r2_url, r2_key, asset_metadata)
        """
        output_path = os.path.join(OUTPUTS_DIR, self.drama.id, "scenes", f"{node.entity_id}.png")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Get reference images from character dependencies
        reference_images = []
        # TODO: Extract character references from dependency_results if needed

        result = generate_image(
            prompt=node.prompt,
            output_path=output_path,
            reference_images=reference_images if reference_images else None
        )

        r2_url, r2_key, asset_metadata = self._upload_to_r2(
            file_path=result["path"],
            asset_type="image",
            tag="storyboard",
            metadata={
                "scene_id": node.entity_id,
                "episode_id": node.metadata.get("episode_id"),
                "type": "scene_storyboard"
            }
        )

        # Log generation success with paths
        scene_id = node.entity_id
        episode_id = node.metadata.get("episode_id", "unknown")
        print(f"✓ Scene storyboard generation completed for {episode_id}/{scene_id}. local_path: {result['path']}, public_url: {r2_url}")

        return result["path"], r2_url, r2_key, asset_metadata

    def _generate_scene_asset(self, node: DAGNode, dependency_results: Dict) -> Tuple[str, str, str, Dict]:
        """Generate scene asset (storyboard image or video clip).

        Returns:
            (result_path, r2_url, r2_key, asset_metadata)
        """
        asset_kind = node.metadata.get("asset_kind")
        scene_id = node.metadata.get("scene_id")
        episode_id = node.metadata.get("episode_id")

        if asset_kind == "video" or asset_kind == AssetKind.video:
            # Generate video clip
            duration = node.metadata.get("duration", 10)

            result_path = generate_video_sora(
                prompt=node.prompt,
                drama_id=self.drama.id,
                asset_id=node.entity_id,
                duration=duration
            )

            r2_url, r2_key, asset_metadata = self._upload_to_r2(
                file_path=result_path,
                asset_type="video",
                tag="clip",
                metadata={
                    "scene_id": scene_id,
                    "episode_id": episode_id,
                    "type": "scene_video_clip",
                    "duration": duration
                }
            )

            # Log generation success with paths
            print(f"✓ Scene video clip generation completed for {episode_id}/{scene_id}/{node.entity_id}. local_path: {result_path}, public_url: {r2_url}")
        else:
            # Generate storyboard image
            output_path = os.path.join(OUTPUTS_DIR, self.drama.id, "scenes", f"{node.entity_id}.png")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            result = generate_image(
                prompt=node.prompt,
                output_path=output_path
            )

            r2_url, r2_key, asset_metadata = self._upload_to_r2(
                file_path=result["path"],
                asset_type="image",
                tag="storyboard",
                metadata={
                    "scene_id": scene_id,
                    "episode_id": episode_id,
                    "type": "scene_storyboard"
                }
            )
            result_path = result["path"]

            # Log generation success with paths
            print(f"✓ Scene storyboard asset generation completed for {episode_id}/{scene_id}/{node.entity_id}. local_path: {result_path}, public_url: {r2_url}")

        return result_path, r2_url, r2_key, asset_metadata

    def _upload_to_r2(self, file_path: str, asset_type: str, tag: str, metadata: Dict) -> Tuple[str, str, Dict]:
        """Upload file to R2 storage.

        Returns:
            (r2_url, r2_key, asset_metadata)
        """
        try:
            lib = AssetLibrary(user_id=self.user_id, project_name=self.project_name)

            with open(file_path, 'rb') as f:
                content = f.read()

            filename = os.path.basename(file_path)

            asset_metadata = lib.upload_asset(
                content=content,
                asset_type=asset_type,
                tag=tag,
                filename=filename,
                metadata={
                    'drama_id': self.drama.id,
                    'source': 'ai_generation',
                    **metadata
                }
            )

            r2_url = asset_metadata.get('public_url')
            r2_key = asset_metadata.get('r2_key')

            logger.info(f"✓ Uploaded to R2: {r2_url}")
            return r2_url, r2_key, asset_metadata

        except Exception as e:
            logger.error(f"Failed to upload to R2: {e}")
            return None, None, None

    def _update_drama_model(self, node: DAGNode, result_path: str, r2_url: str):
        """Update drama model with generation results."""
        if node.node_type == "character":
            for char in self.drama.characters:
                if char.id == node.entity_id:
                    char.url = r2_url
                    break
        elif node.node_type == "scene_asset" or node.node_type == "character_asset":
            # Find and update the asset
            for episode in self.drama.episodes:
                for scene in episode.scenes:
                    for asset in scene.assets:
                        if asset.id == node.entity_id:
                            asset.url = r2_url
                            return
            # Check character assets
            for char in self.drama.characters:
                for asset in char.assets:
                    if asset.id == node.entity_id:
                        asset.url = r2_url
                        return

    def execute_level(self, level_nodes: List[DAGNode], dependency_results: Dict[str, Dict]) -> List[Dict]:
        """Execute all nodes in a level in parallel.

        Args:
            level_nodes: List of nodes to execute
            dependency_results: Results from dependency nodes

        Returns:
            List of updated job data
        """
        results = []

        def execute_wrapper(node):
            try:
                job = self.jobs[node.node_id]
                updated_job = self.execute_node(node, job, dependency_results)
                results.append(updated_job)
                # Update jobs dict and dependency results
                self.jobs[node.node_id] = updated_job
                dependency_results[node.node_id] = updated_job
            except Exception as e:
                logger.error(f"Error executing node {node.node_id}: {e}")

        threads = []
        for node in level_nodes:
            thread = threading.Thread(target=execute_wrapper, args=(node,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        return results

    def execute_dag(self, resume: bool = False) -> Dict:
        """Execute the complete hierarchical DAG.

        Args:
            resume: If True, resume from existing jobs

        Returns:
            Execution status dict
        """
        logger.info(f"Starting hierarchical DAG execution for drama {self.drama.id}")

        # Build hierarchical DAG
        dag = self.build_hierarchical_dag()
        logger.info(f"Built DAG with {len(dag)} nodes across {len(set(n.hierarchy_level for n in self.nodes.values()))} hierarchy levels")

        # Get execution order
        levels = self.topological_sort(dag)

        # Get or create jobs
        self.get_or_create_jobs(resume=resume)

        # Track dependency results
        dependency_results = {}

        # Execute level by level
        for level_index, level_node_ids in enumerate(levels):
            logger.info(f"Executing level {level_index}: {len(level_node_ids)} nodes")

            # Get nodes for this level
            level_nodes = [self.nodes[node_id] for node_id in level_node_ids]

            # Skip nodes that are already completed (if resuming)
            if resume:
                level_nodes = [
                    node for node in level_nodes
                    if self.jobs[node.node_id].get("status") != "completed"
                ]

            if not level_nodes:
                logger.info(f"Level {level_index} already completed, skipping")
                continue

            # Execute level in parallel
            level_results = self.execute_level(level_nodes, dependency_results)

        # Get final status
        return self.get_execution_status()

    def get_execution_status(self) -> Dict:
        """Get current execution status.

        Returns:
            Execution status dict
        """
        job_list = list(self.jobs.values())

        # Count statuses
        total = len(job_list)
        completed = sum(1 for j in job_list if j.get("status") == "completed")
        failed = sum(1 for j in job_list if j.get("status") == "failed")
        running = sum(1 for j in job_list if j.get("status") == "running")
        pending = sum(1 for j in job_list if j.get("status") == "pending")

        # Determine overall status
        if completed == total and total > 0:
            overall_status = "completed"
        elif failed > 0 and (completed + failed) == total:
            overall_status = "failed"
        elif running > 0:
            overall_status = "running"
        else:
            overall_status = "pending"

        return {
            "dag_id": self.dag_id,
            "drama_id": self.drama.id,
            "parent_job_id": self.parent_job_id,
            "status": overall_status,
            "total_jobs": total,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "running_jobs": running,
            "pending_jobs": pending,
            "jobs": job_list
        }
