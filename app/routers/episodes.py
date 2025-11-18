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
