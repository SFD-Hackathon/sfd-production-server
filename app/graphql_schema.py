"""GraphQL schema for Drama API using Strawberry"""

import strawberry
from typing import List, Optional
import logging
from app.models import Drama as DramaPydantic, Character as CharacterPydantic, Episode as EpisodePydantic, Scene as ScenePydantic
from app.dal import get_supabase_client, DramaRepository
from app.ai_service import get_ai_service

logger = logging.getLogger(__name__)

# TODO: Replace with proper authentication (JWT, API key, etc.)
DEFAULT_USER_ID = "a1111111-1111-1111-1111-111111111111"  # Demo user UUID


def get_drama_repository() -> DramaRepository:
    """Get DramaRepository instance with Supabase client"""
    client = get_supabase_client()
    return DramaRepository(client)


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
class Scene:
    id: str
    description: str
    imageUrl: Optional[str] = strawberry.field(default=None, name="imageUrl")
    videoUrl: Optional[str] = strawberry.field(default=None, name="videoUrl")


@strawberry.type
class Episode:
    id: str
    title: str
    description: str
    url: Optional[str] = None
    scenes: List[Scene]


@strawberry.type
class DramaSummary:
    """Lightweight drama summary from index (fast)"""
    id: str
    title: str
    description: str
    premise: str
    url: Optional[str] = None
    createdAt: str = strawberry.field(name="createdAt")
    updatedAt: str = strawberry.field(name="updatedAt")


@strawberry.type
class Drama:
    id: str
    title: str
    description: str
    premise: str
    url: Optional[str] = None
    characters: List[Character]
    episodes: List[Episode]

    @strawberry.field
    def cover_photo(self) -> Optional[str]:
        """Alias for url field - the drama cover photo URL"""
        return self.url


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
        repo = get_drama_repository()
        drama_pydantic = await repo.get_drama_complete(id)
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
                    scenes=[
                        Scene(
                            id=scene.id,
                            description=scene.description,
                            imageUrl=scene.image_url,
                            videoUrl=scene.video_url,
                        )
                        for scene in ep.scenes
                    ],
                )
                for ep in drama_pydantic.episodes
            ],
        )

    @strawberry.field
    async def drama_summaries(self, limit: int = 100, user_id: Optional[str] = None) -> List[DramaSummary]:
        """
        Get drama summaries (fast, lightweight - no nested data).

        Args:
            limit: Maximum number of dramas to return
            user_id: Optional user ID to filter dramas (defaults to DEFAULT_USER_ID)
        """
        repo = get_drama_repository()
        # TODO: Get user_id from auth context instead of parameter
        uid = user_id or DEFAULT_USER_ID
        summaries = await repo.get_user_dramas(user_id=uid, limit=limit)

        return [
            DramaSummary(
                id=summary["id"],
                title=summary["title"],
                description=summary["description"],
                premise=summary["premise"],
                url=summary.get("url") or summary.get("cover_url"),
                createdAt=summary["created_at"],
                updatedAt=summary["updated_at"],
            )
            for summary in summaries
        ]

    @strawberry.field
    async def dramas(self, limit: int = 100, offset: int = 0) -> List[Drama]:
        """
        Get all dramas with full details (slower, fetches nested data from Supabase).

        Args:
            limit: Maximum number of dramas to return
            offset: Number of dramas to skip (for pagination)
        """
        repo = get_drama_repository()
        drama_list, _ = await repo.list_dramas(limit=limit, offset=offset)

        return [
            Drama(
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
                        scenes=[
                            Scene(
                                id=scene.id,
                                description=scene.description,
                                imageUrl=scene.image_url,
                                videoUrl=scene.video_url,
                            )
                            for scene in ep.scenes
                        ],
                    )
                    for ep in drama_pydantic.episodes
                ],
            )
            for drama_pydantic in drama_list
        ]



# Mutation type
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def generate_character_image(
        self,
        drama_id: str,
        character_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Character]:
        """
        Generate image for a character.

        Args:
            drama_id: Drama ID
            character_id: Character ID
            user_id: Optional user ID (defaults to DEFAULT_USER_ID)
        """
        # TODO: Get user_id from auth context instead of parameter
        uid = user_id or DEFAULT_USER_ID

        repo = get_drama_repository()
        drama_pydantic = await repo.get_drama_complete(drama_id)
        if not drama_pydantic:
            logger.error(f"Drama {drama_id} not found")
            return None

        # Find character
        character = next((c for c in drama_pydantic.characters if c.id == character_id), None)
        if not character:
            logger.error(f"Character {character_id} not found in drama {drama_id}")
            return None

        # Generate image
        ai_service = get_ai_service()
        image_url = await ai_service.generate_character_image(
            drama_id=drama_id,
            character=character,
        )

        # Update character
        character.url = image_url
        await repo.save_drama_complete(drama_pydantic, user_id=uid)

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
    async def generate_cover_photo(
        self,
        drama_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Drama]:
        """
        Generate drama cover photo.

        Args:
            drama_id: Drama ID
            user_id: Optional user ID (defaults to DEFAULT_USER_ID)
        """
        # TODO: Get user_id from auth context instead of parameter
        uid = user_id or DEFAULT_USER_ID

        repo = get_drama_repository()
        drama_pydantic = await repo.get_drama_complete(drama_id)
        if not drama_pydantic:
            logger.error(f"Drama {drama_id} not found")
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
        await repo.save_drama_complete(drama_pydantic, user_id=uid)

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
                    scenes=[
                        Scene(
                            id=scene.id,
                            description=scene.description,
                            imageUrl=scene.image_url,
                            videoUrl=scene.video_url,
                        )
                        for scene in ep.scenes
                    ],
                )
                for ep in drama_pydantic.episodes
            ],
        )


# Create schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
