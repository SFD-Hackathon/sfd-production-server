"""Asset management endpoints"""

from fastapi import APIRouter, HTTPException, status

from app.models import Asset, AssetUpdate, AssetListResponse
from app.storage import storage

router = APIRouter()


@router.get("/{drama_id}/episodes/{episode_id}/scenes/{scene_id}/assets", response_model=AssetListResponse)
async def list_assets(drama_id: str, episode_id: str, scene_id: str):
    """List all assets in a scene"""
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

    return AssetListResponse(assets=scene.assets)


@router.get("/{drama_id}/episodes/{episode_id}/scenes/{scene_id}/assets/{asset_id}", response_model=Asset)
async def get_asset(
    drama_id: str, episode_id: str, scene_id: str, asset_id: str
):
    """Get a specific asset"""
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

    asset = next((a for a in scene.assets if a.id == asset_id), None)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Asset not found", "message": f"Asset {asset_id} not found"},
        )

    return asset


@router.patch("/{drama_id}/episodes/{episode_id}/scenes/{scene_id}/assets/{asset_id}", response_model=Asset)
async def update_asset(
    drama_id: str,
    episode_id: str,
    scene_id: str,
    asset_id: str,
    update: AssetUpdate,
):
    """Update an asset"""
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

    asset = next((a for a in scene.assets if a.id == asset_id), None)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Asset not found", "message": f"Asset {asset_id} not found"},
        )

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asset, field, value)

    # Save updated drama
    await storage.save_drama(drama)

    return asset
