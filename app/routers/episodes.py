"""Episode management endpoints"""

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
import random
import string

from app.models import Episode, EpisodeUpdate, EpisodeListResponse, JobResponse, JobStatus, JobType
from app.storage import storage
from app.job_manager import job_manager

router = APIRouter()


def generate_id(prefix: str = "job") -> str:
    """Generate a random ID"""
    random_part = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"{prefix}_{random_part}"


@router.get("/{drama_id}/episodes", response_model=EpisodeListResponse)
async def list_episodes(drama_id: str):
    """List all episodes in a drama"""
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )
    return EpisodeListResponse(episodes=drama.episodes)


@router.get("/{drama_id}/episodes/{episode_id}", response_model=Episode)
async def get_episode(drama_id: str, episode_id: str):
    """Get a specific episode"""
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    episode = next((e for e in drama.episodes if e.id == episode_id), None)
    if not episode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Episode not found", "message": f"Episode {episode_id} not found"},
        )

    return episode


@router.patch("/{drama_id}/episodes/{episode_id}", response_model=Episode)
async def update_episode(drama_id: str, episode_id: str, update: EpisodeUpdate):
    """Update an episode"""
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    episode = next((e for e in drama.episodes if e.id == episode_id), None)
    if not episode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Episode not found", "message": f"Episode {episode_id} not found"},
        )

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(episode, field, value)

    # Save updated drama
    await storage.save_drama(drama)

    return episode


@router.post("/{drama_id}/episodes/{episode_id}/generate", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_episode_assets(drama_id: str, episode_id: str, background_tasks: BackgroundTasks):
    """
    Generate all assets for an episode

    Triggers asset generation jobs for all assets in the episode hierarchy
    (scene storyboards and scene video clips).

    Uses the hierarchical DAG approach:
    - Generates scenes (storyboards) first
    - Then generates scene assets (clips) that depend on scenes

    Returns immediately with a job ID. Poll job status to track progress.
    """
    # Check if drama exists
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    # Check if episode exists
    episode = next((e for e in drama.episodes if e.id == episode_id), None)
    if not episode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Episode not found", "message": f"Episode {episode_id} not found"},
        )

    # Generate job ID
    job_id = generate_id("job")

    # Create job
    job_manager.create_job(job_id, drama_id, JobType.generate_image)

    # Queue background task for episode asset generation
    async def execute_episode_generation():
        try:
            from app.hierarchical_dag_engine import HierarchicalDAGExecutor

            # Create a sub-drama with just this episode
            # (DAG executor will only process assets for this episode)
            executor = HierarchicalDAGExecutor(
                drama=drama,
                user_id="10000",
                project_name=drama_id
            )

            # Build DAG and filter to only this episode's nodes
            dag = executor.build_hierarchical_dag()

            # Filter nodes to only include this episode and its scenes/assets
            filtered_nodes = {
                node_id: node
                for node_id, node in executor.nodes.items()
                if node.metadata.get("episode_id") == episode_id or
                   (node.node_type == "episode" and node.entity_id == episode_id)
            }

            executor.nodes = filtered_nodes

            # Execute filtered DAG
            result = executor.execute_dag()

            # Update job with results
            job_manager.update_job_status(
                job_id,
                JobStatus.completed if result["status"] == "completed" else JobStatus.failed,
                result=result
            )
        except Exception as e:
            job_manager.update_job_status(job_id, JobStatus.failed, error=str(e))

    background_tasks.add_task(execute_episode_generation)

    return JobResponse(
        dramaId=drama_id,
        jobId=job_id,
        status=JobStatus.pending,
        message=f"Episode asset generation queued. Check status at: https://api.shortformdramas.com/dramas/{drama_id}/jobs/{job_id}",
    )
