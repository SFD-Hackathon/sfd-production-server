"""Episode management endpoints"""

from fastapi import APIRouter, HTTPException, status

from app.models import Episode, EpisodeUpdate, EpisodeListResponse
from app.storage import storage

router = APIRouter()


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


@router.post("/{drama_id}/episodes/{episode_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_episode_assets(drama_id: str, episode_id: str):
    """
    Generate all assets for an episode

    Triggers asset generation jobs for all assets in the episode hierarchy
    (episode assets and all scene assets).

    **Status:** Not implemented yet - placeholder for future asset generation
    """
    # TODO: Implement episode asset generation logic
    # This will:
    # 1. Get all assets for this episode and its scenes
    # 2. For each asset without a URL, create a generation job
    # 3. Queue jobs for image/video generation
    # 4. Return list of created job IDs

    return {
        "message": "Episode asset generation not implemented yet",
        "dramaId": drama_id,
        "episodeId": episode_id,
        "status": "not_implemented"
    }
