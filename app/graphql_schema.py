"""GraphQL schema for Drama API using Strawberry"""

import strawberry
from typing import List, Optional
from app.models import Drama as DramaPydantic, Character as CharacterPydantic, Episode as EpisodePydantic
from app.storage import storage
from app.ai_service import get_ai_service


# GraphQL Types (converted from Pydantic models)
@strawberry.type
class Character:
    id: str
    name: str
    description: str
    gender: str
    voice_description: str
    main: bool
    url: Optional[str] = None


@strawberry.type
class Episode:
    id: str
    title: str
    description: str
    url: Optional[str] = None


@strawberry.type
class Drama:
    id: str
    title: str
    description: str
    premise: str
    url: Optional[str] = None
    characters: List[Character]
    episodes: List[Episode]


@strawberry.type
class DramaSummary:
    """Lightweight drama summary for list queries"""
    id: str
    title: str
    description: str
    url: Optional[str] = None
    character_count: int
    episode_count: int


# Input types for mutations
@strawberry.input
class CreateDramaInput:
    premise: str
    model: str = "gemini-3-pro-preview"


# Query type
@strawberry.type
class Query:
    @strawberry.field
    async def drama(self, id: str) -> Optional[Drama]:
        """Get a drama by ID"""
        drama_pydantic = await storage.get_drama(id)
        if not drama_pydantic:
            return None

        return Drama(
            id=drama_pydantic.id,
            title=drama_pydantic.title,
            description=drama_pydantic.description,
            premise=drama_pydantic.premise,
            url=drama_pydantic.url,
            characters=[
                Character(
                    id=char.id,
                    name=char.name,
                    description=char.description,
                    gender=char.gender,
                    voice_description=char.voice_description,
                    main=char.main,
                    url=char.url,
                )
                for char in drama_pydantic.characters
            ],
            episodes=[
                Episode(
                    id=ep.id,
                    title=ep.title,
                    description=ep.description,
                    url=ep.url,
                )
                for ep in drama_pydantic.episodes
            ],
        )

    @strawberry.field
    async def dramas(self, limit: Optional[int] = 10) -> List[DramaSummary]:
        """
        Get all dramas (lightweight summary with pagination)

        Args:
            limit: Maximum number of dramas to return (default: 10, max: 100)
        """
        # Cap limit at 100
        limit = min(limit or 10, 100)

        # Use storage's built-in pagination
        dramas_list, _ = await storage.list_dramas(limit=limit)

        # Convert to summaries (lightweight - no nested objects)
        summaries = []
        for drama_pydantic in dramas_list:
            summaries.append(
                DramaSummary(
                    id=drama_pydantic.id,
                    title=drama_pydantic.title,
                    description=drama_pydantic.description,
                    url=drama_pydantic.url,
                    character_count=len(drama_pydantic.characters),
                    episode_count=len(drama_pydantic.episodes),
                )
            )

        return summaries

    @strawberry.field
    async def cover_photo(self, drama_id: str) -> Optional[str]:
        """Get drama cover photo URL"""
        drama_pydantic = await storage.get_drama(drama_id)
        if not drama_pydantic:
            return None
        return drama_pydantic.url


# Mutation type
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def generate_character_image(self, drama_id: str, character_id: str) -> Optional[Character]:
        """Generate image for a character"""
        drama_pydantic = await storage.get_drama(drama_id)
        if not drama_pydantic:
            return None

        # Find character
        character = next((c for c in drama_pydantic.characters if c.id == character_id), None)
        if not character:
            return None

        # Generate image
        ai_service = get_ai_service()
        image_url = await ai_service.generate_character_image(
            drama_id=drama_id,
            character=character,
        )

        # Update character
        character.url = image_url
        await storage.save_drama(drama_pydantic)

        return Character(
            id=character.id,
            name=character.name,
            description=character.description,
            gender=character.gender,
            voice_description=character.voice_description,
            main=character.main,
            url=character.url,
        )

    @strawberry.mutation
    async def generate_cover_photo(self, drama_id: str) -> Optional[Drama]:
        """Generate drama cover photo"""
        drama_pydantic = await storage.get_drama(drama_id)
        if not drama_pydantic:
            return None

        # Check that all main characters have images
        main_characters = [char for char in drama_pydantic.characters if char.main]
        if not main_characters:
            raise Exception("Drama must have at least one main character")

        characters_without_images = [char.name for char in main_characters if not char.url]
        if characters_without_images:
            raise Exception(f"All main characters must have images: {', '.join(characters_without_images)}")

        # Generate cover
        ai_service = get_ai_service()
        cover_url = await ai_service.generate_drama_cover_image(
            drama_id=drama_id,
            drama=drama_pydantic,
        )

        # Update drama
        drama_pydantic.url = cover_url
        await storage.save_drama(drama_pydantic)

        return Drama(
            id=drama_pydantic.id,
            title=drama_pydantic.title,
            description=drama_pydantic.description,
            premise=drama_pydantic.premise,
            url=drama_pydantic.url,
            characters=[
                Character(
                    id=char.id,
                    name=char.name,
                    description=char.description,
                    gender=char.gender,
                    voice_description=char.voice_description,
                    main=char.main,
                    url=char.url,
                )
                for char in drama_pydantic.characters
            ],
            episodes=[
                Episode(
                    id=ep.id,
                    title=ep.title,
                    description=ep.description,
                    url=ep.url,
                )
                for ep in drama_pydantic.episodes
            ],
        )


# Create schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
