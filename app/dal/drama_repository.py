"""
Drama Repository

Data access layer for drama-related operations with nested data handling.
"""

import logging
from typing import Dict, List, Optional
from supabase import Client
from app.dal.base import BaseRepository
from app.models import Drama, Character, Episode, Scene

logger = logging.getLogger(__name__)


class DramaRepository(BaseRepository):
    """Repository for drama table and related nested tables"""

    def __init__(self, client: Client):
        super().__init__(client, "dramas")
        self.characters_table = client.table("characters")
        self.episodes_table = client.table("episodes")
        self.scenes_table = client.table("scenes")

    async def create_drama(
        self,
        drama_id: str,
        user_id: str,
        title: str,
        description: str,
        premise: str,
        url: Optional[str] = None,
        status: str = "pending",
    ) -> Optional[Dict]:
        """
        Create a new drama record.

        Args:
            drama_id: External drama ID
            user_id: User who owns the drama
            title: Drama title
            description: Drama description
            premise: Original user prompt
            url: Optional cover photo URL
            status: Drama status

        Returns:
            Created drama record or None if failed
        """
        drama_data = {
            "id": drama_id,
            "user_id": user_id,
            "title": title,
            "description": description,
            "premise": premise,
            "status": status,
        }

        if url:
            drama_data["url"] = url
            drama_data["cover_url"] = url  # Also set cover_url

        return await self.create(drama_data)

    async def get_drama(self, drama_id: str) -> Optional[Dict]:
        """Get drama by ID (without nested data)"""
        return await self.find_by_id("id", drama_id)

    async def get_drama_complete(self, drama_id: str) -> Optional[Drama]:
        """
        Get complete drama with all nested data (characters, episodes, scenes).

        Args:
            drama_id: Drama ID

        Returns:
            Drama Pydantic model with nested data or None if not found
        """
        try:
            # Get drama
            drama_data = await self.get_drama(drama_id)
            if not drama_data:
                return None

            # Get characters
            characters = await self.get_drama_characters(drama_id)

            # Get episodes with scenes
            episodes = await self.get_drama_episodes(drama_id)

            # Construct Drama model
            drama = Drama(
                id=drama_data["id"],
                title=drama_data["title"],
                description=drama_data["description"],
                premise=drama_data["premise"],
                url=drama_data.get("url"),
                characters=[
                    Character(
                        id=char["id"],
                        name=char["name"],
                        description=char["description"],
                        gender=char["gender"],
                        voice_description=char["voice_description"],
                        main=char["is_main"],
                        url=char.get("url"),
                    )
                    for char in characters
                ],
                episodes=[
                    Episode(
                        id=ep["id"],
                        title=ep["title"],
                        description=ep["description"],
                        url=ep.get("url"),
                        scenes=ep.get("scenes", []),
                    )
                    for ep in episodes
                ],
            )

            return drama
        except Exception as e:
            logger.error(f"Error getting complete drama {drama_id}: {e}")
            return None

    async def save_drama_complete(
        self,
        drama: Drama,
        user_id: str
    ) -> Optional[Dict]:
        """
        Save complete drama with all nested data.

        This performs upserts for drama, characters, episodes, and scenes.

        Args:
            drama: Drama Pydantic model
            user_id: User who owns the drama

        Returns:
            Saved drama record or None if failed
        """
        try:
            # Upsert drama
            drama_data = {
                "id": drama.id,
                "user_id": user_id,
                "title": drama.title,
                "description": drama.description,
                "premise": drama.premise,
                "status": "completed",  # Assume completed when saving complete data
            }

            if drama.url:
                drama_data["url"] = drama.url
                drama_data["cover_url"] = drama.url

            drama_record = await self.upsert(drama_data)

            # Bulk upsert characters
            if drama.characters:
                await self._save_characters(drama.id, user_id, drama.characters)

            # Bulk upsert episodes with scenes
            if drama.episodes:
                await self._save_episodes(drama.id, user_id, drama.episodes)

            return drama_record
        except Exception as e:
            logger.error(f"Error saving complete drama {drama.id}: {e}")
            return None

    async def _save_characters(
        self,
        drama_id: str,
        user_id: str,
        characters: List[Character]
    ):
        """Save characters for a drama"""
        try:
            characters_data = [
                {
                    "id": char.id,
                    "drama_id": drama_id,
                    "user_id": user_id,
                    "name": char.name,
                    "description": char.description,
                    "gender": char.gender,
                    "voice_description": char.voice_description,
                    "is_main": char.main,
                    "url": char.url,
                }
                for char in characters
            ]

            self.characters_table.upsert(characters_data).execute()
        except Exception as e:
            logger.error(f"Error saving characters for drama {drama_id}: {e}")

    async def _save_episodes(
        self,
        drama_id: str,
        user_id: str,
        episodes: List[Episode]
    ):
        """Save episodes and scenes for a drama"""
        try:
            episodes_data = []
            all_scenes_data = []

            for idx, episode in enumerate(episodes):
                episodes_data.append({
                    "id": episode.id,
                    "drama_id": drama_id,
                    "user_id": user_id,
                    "title": episode.title,
                    "description": episode.description,
                    "url": episode.url,
                    "sequence_number": idx + 1,
                })

                # Collect scenes for this episode
                if episode.scenes:
                    for scene_idx, scene in enumerate(episode.scenes):
                        all_scenes_data.append({
                            "id": scene.id,
                            "episode_id": episode.id,
                            "drama_id": drama_id,
                            "user_id": user_id,
                            "description": scene.description,
                            "image_url": scene.image_url,
                            "video_url": scene.video_url,
                            "sequence_number": scene_idx + 1,
                        })

            # Bulk upsert episodes
            self.episodes_table.upsert(episodes_data).execute()

            # Bulk upsert scenes
            if all_scenes_data:
                self.scenes_table.upsert(all_scenes_data).execute()

        except Exception as e:
            logger.error(f"Error saving episodes for drama {drama_id}: {e}")

    async def get_drama_characters(self, drama_id: str) -> List[Dict]:
        """Get all characters for a drama"""
        try:
            response = (
                self.characters_table.select("*")
                .eq("drama_id", drama_id)
                .order("created_at")
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error getting characters for drama {drama_id}: {e}")
            return []

    async def get_drama_episodes(self, drama_id: str) -> List[Dict]:
        """Get all episodes for a drama (with scenes)"""
        try:
            # Get episodes
            episodes_response = (
                self.episodes_table.select("*")
                .eq("drama_id", drama_id)
                .order("sequence_number")
                .execute()
            )

            episodes = episodes_response.data

            # Get scenes for each episode
            for episode in episodes:
                scenes_response = (
                    self.scenes_table.select("*")
                    .eq("episode_id", episode["id"])
                    .order("sequence_number")
                    .execute()
                )
                episode["scenes"] = [
                    Scene(
                        id=scene["id"],
                        description=scene["description"],
                        image_url=scene.get("image_url"),
                        video_url=scene.get("video_url"),
                    )
                    for scene in scenes_response.data
                ]

            return episodes
        except Exception as e:
            logger.error(f"Error getting episodes for drama {drama_id}: {e}")
            return []

    async def update_drama_status(
        self,
        drama_id: str,
        status: str
    ) -> Optional[Dict]:
        """Update drama status"""
        return await self.update("id", drama_id, {"status": status})

    async def update_episode_count(
        self,
        drama_id: str,
        episode_count: int
    ) -> Optional[Dict]:
        """Update drama episode count"""
        return await self.update("id", drama_id, {"episode_count": episode_count})

    async def delete_drama_complete(self, drama_id: str) -> bool:
        """
        Delete drama and all related data (cascades to characters, episodes, scenes).

        Args:
            drama_id: Drama ID

        Returns:
            True if successful, False otherwise
        """
        return await self.delete("id", drama_id)

    async def get_user_dramas(
        self,
        user_id: str,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all dramas for a user.

        Args:
            user_id: User ID
            limit: Maximum results (default: 100)
            status: Optional status filter

        Returns:
            List of drama records
        """
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status

        return await self.find_all(
            filters=filters,
            limit=limit,
            order_by="created_at",
            ascending=False
        )

    async def list_dramas(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[Drama], Optional[str]]:
        """
        List all dramas (for admin/system use).

        Args:
            limit: Maximum results
            offset: Number to skip

        Returns:
            Tuple of (dramas list, next cursor)
        """
        dramas_data = await self.find_all(
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False
        )

        dramas = []
        for drama_data in dramas_data:
            drama = await self.get_drama_complete(drama_data["id"])
            if drama:
                dramas.append(drama)

        # Simple cursor pagination (offset-based)
        next_cursor = str(offset + limit) if len(dramas_data) == limit else None

        return dramas, next_cursor
