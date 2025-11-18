"""Character management endpoints"""

from fastapi import APIRouter, HTTPException, status

from app.models import Character, CharacterUpdate, CharacterListResponse
from app.storage import storage

router = APIRouter()


@router.get("/{drama_id}/characters", response_model=CharacterListResponse)
async def list_characters(drama_id: str):
    """List all characters in a drama"""
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )
    return CharacterListResponse(characters=drama.characters)


@router.get("/{drama_id}/characters/{character_id}", response_model=Character)
async def get_character(drama_id: str, character_id: str):
    """Get a specific character"""
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    character = next((c for c in drama.characters if c.id == character_id), None)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Character not found", "message": f"Character {character_id} not found"},
        )

    return character


@router.patch("/{drama_id}/characters/{character_id}", response_model=Character)
async def update_character(
    drama_id: str, character_id: str, update: CharacterUpdate
):
    """Update a character"""
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    character = next((c for c in drama.characters if c.id == character_id), None)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Character not found", "message": f"Character {character_id} not found"},
        )

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(character, field, value)

    # Save updated drama
    await storage.save_drama(drama)

    return character


@router.post("/{drama_id}/characters/{character_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_character_assets(drama_id: str, character_id: str):
    """
    Generate all assets for a character

    Triggers asset generation jobs for all assets associated with this character.

    **Status:** Not implemented yet - placeholder for future asset generation
    """
    # TODO: Implement character asset generation logic
    # This will:
    # 1. Get all assets for this character
    # 2. For each asset without a URL, create a generation job
    # 3. Queue jobs for character images/videos
    # 4. Return list of created job IDs

    return {
        "message": "Character asset generation not implemented yet",
        "dramaId": drama_id,
        "characterId": character_id,
        "status": "not_implemented"
    }
