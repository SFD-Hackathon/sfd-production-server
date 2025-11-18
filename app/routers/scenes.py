"""Scene management endpoints"""

from fastapi import APIRouter, HTTPException, status

from app.models import Scene, SceneUpdate, SceneListResponse
from app.storage import storage

router = APIRouter()


@router.get("/{drama_id}/episodes/{episode_id}/scenes", response_model=SceneListResponse)
async def list_scenes(drama_id: str, episode_id: str):
    """List all scenes in an episode"""
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

    return SceneListResponse(scenes=episode.scenes)


@router.get("/{drama_id}/episodes/{episode_id}/scenes/{scene_id}", response_model=Scene)
async def get_scene(drama_id: str, episode_id: str, scene_id: str):
    """Get a specific scene"""
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

    scene = next((s for s in episode.scenes if s.id == scene_id), None)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Scene not found", "message": f"Scene {scene_id} not found"},
        )

    return scene


@router.patch("/{drama_id}/episodes/{episode_id}/scenes/{scene_id}", response_model=Scene)
async def update_scene(
    drama_id: str, episode_id: str, scene_id: str, update: SceneUpdate
):
    """Update a scene"""
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

    scene = next((s for s in episode.scenes if s.id == scene_id), None)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Scene not found", "message": f"Scene {scene_id} not found"},
        )

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scene, field, value)

    # Save updated drama
    await storage.save_drama(drama)

    return scene


@router.post("/{drama_id}/episodes/{episode_id}/scenes/{scene_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_scene_assets(drama_id: str, episode_id: str, scene_id: str):
    """
    Generate all assets for a scene

    Triggers asset generation jobs for all assets in this scene.

    **Status:** Not implemented yet - placeholder for future asset generation
    """
    # TODO: Implement scene asset generation logic
    # This will:
    # 1. Get all assets for this scene
    # 2. For each asset without a URL, create a generation job
    # 3. Queue jobs for image/video generation
    # 4. Return list of created job IDs

    return {
        "message": "Scene asset generation not implemented yet",
        "dramaId": drama_id,
        "episodeId": episode_id,
        "sceneId": scene_id,
        "status": "not_implemented"
    }
