"""GraphQL schema for Drama API using Strawberry"""

import strawberry
from typing import List, Optional, Any
from datetime import datetime
from app.models import Drama as DramaPydantic, Character as CharacterPydantic, Episode as EpisodePydantic, Scene as ScenePydantic
from app.storage import storage
from app.ai_service import get_ai_service
from app.job_storage import get_storage as get_job_storage


# GraphQL Types (converted from Pydantic models)
@strawberry.type
class Job:
    """Job status for asset generation"""
    jobId: str = strawberry.field(name="jobId")
    dramaId: str = strawberry.field(name="dramaId")
    assetId: Optional[str] = strawberry.field(default=None, name="assetId")
    type: str
    status: str
    prompt: Optional[str] = None
    r2Url: Optional[str] = strawberry.field(default=None, name="r2Url")
    createdAt: str = strawberry.field(name="createdAt")
    startedAt: Optional[str] = strawberry.field(default=None, name="startedAt")
    completedAt: Optional[str] = strawberry.field(default=None, name="completedAt")
    error: Optional[str] = None

    # Hierarchical job fields
    parentJobId: Optional[str] = strawberry.field(default=None, name="parentJobId")
    childJobs: Optional[List[str]] = strawberry.field(default=None, name="childJobs")
    totalJobs: Optional[int] = strawberry.field(default=None, name="totalJobs")
    completedJobs: Optional[int] = strawberry.field(default=None, name="completedJobs")
    failedJobs: Optional[int] = strawberry.field(default=None, name="failedJobs")
    runningJobs: Optional[int] = strawberry.field(default=None, name="runningJobs")


@strawberry.type
class Character:
    id: str
    name: str
    description: str
    gender: str
    voice_description: str
    main: bool
    url: Optional[str] = None
    _drama_id: strawberry.Private[str] = ""

    @strawberry.field
    def jobs(self) -> List["Job"]:
        """Get jobs for this character"""
        job_storage = get_job_storage()
        jobs_data = job_storage.list_jobs(drama_id=self._drama_id)

        # Filter jobs related to this character
        character_jobs = [
            job for job in jobs_data
            if job.get("asset_id") == self.id or
               job.get("metadata", {}).get("character_id") == self.id
        ]

        return [
            Job(
                jobId=job_data["job_id"],
                dramaId=job_data.get("drama_id", ""),
                assetId=job_data.get("asset_id"),
                type=job_data.get("type", job_data.get("job_type", "unknown")),
                status=job_data["status"],
                prompt=job_data.get("prompt"),
                r2Url=job_data.get("r2_url"),
                createdAt=job_data["created_at"],
                startedAt=job_data.get("started_at"),
                completedAt=job_data.get("completed_at"),
                error=job_data.get("error"),
                parentJobId=job_data.get("parent_job_id"),
                childJobs=job_data.get("child_jobs"),
                totalJobs=job_data.get("total_jobs"),
                completedJobs=job_data.get("completed_jobs"),
                failedJobs=job_data.get("failed_jobs"),
                runningJobs=job_data.get("running_jobs"),
            )
            for job_data in character_jobs
        ]


@strawberry.type
class Scene:
    id: str
    description: str
    imageUrl: Optional[str] = strawberry.field(default=None, name="imageUrl")
    videoUrl: Optional[str] = strawberry.field(default=None, name="videoUrl")
    _drama_id: strawberry.Private[str] = ""
    _episode_id: strawberry.Private[str] = ""

    @strawberry.field
    def jobs(self) -> List["Job"]:
        """Get jobs for this scene"""
        job_storage = get_job_storage()
        jobs_data = job_storage.list_jobs(drama_id=self._drama_id)

        # Filter jobs related to this scene
        scene_jobs = [
            job for job in jobs_data
            if job.get("metadata", {}).get("scene_id") == self.id
        ]

        return [
            Job(
                jobId=job_data["job_id"],
                dramaId=job_data.get("drama_id", ""),
                assetId=job_data.get("asset_id"),
                type=job_data.get("type", job_data.get("job_type", "unknown")),
                status=job_data["status"],
                prompt=job_data.get("prompt"),
                r2Url=job_data.get("r2_url"),
                createdAt=job_data["created_at"],
                startedAt=job_data.get("started_at"),
                completedAt=job_data.get("completed_at"),
                error=job_data.get("error"),
                parentJobId=job_data.get("parent_job_id"),
                childJobs=job_data.get("child_jobs"),
                totalJobs=job_data.get("total_jobs"),
                completedJobs=job_data.get("completed_jobs"),
                failedJobs=job_data.get("failed_jobs"),
                runningJobs=job_data.get("running_jobs"),
            )
            for job_data in scene_jobs
        ]


@strawberry.type
class Episode:
    id: str
    title: str
    description: str
    url: Optional[str] = None
    scenes: List[Scene]
    _drama_id: strawberry.Private[str] = ""

    @strawberry.field
    def jobs(self) -> List["Job"]:
        """Get jobs for this episode"""
        job_storage = get_job_storage()
        jobs_data = job_storage.list_jobs(drama_id=self._drama_id)

        # Filter jobs related to this episode
        episode_jobs = [
            job for job in jobs_data
            if job.get("metadata", {}).get("episode_id") == self.id or
               job.get("asset_id") == self.id
        ]

        return [
            Job(
                jobId=job_data["job_id"],
                dramaId=job_data.get("drama_id", ""),
                assetId=job_data.get("asset_id"),
                type=job_data.get("type", job_data.get("job_type", "unknown")),
                status=job_data["status"],
                prompt=job_data.get("prompt"),
                r2Url=job_data.get("r2_url"),
                createdAt=job_data["created_at"],
                startedAt=job_data.get("started_at"),
                completedAt=job_data.get("completed_at"),
                error=job_data.get("error"),
                parentJobId=job_data.get("parent_job_id"),
                childJobs=job_data.get("child_jobs"),
                totalJobs=job_data.get("total_jobs"),
                completedJobs=job_data.get("completed_jobs"),
                failedJobs=job_data.get("failed_jobs"),
                runningJobs=job_data.get("running_jobs"),
            )
            for job_data in episode_jobs
        ]


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

    @strawberry.field
    def jobs(self) -> List["Job"]:
        """Get all jobs for this drama"""
        job_storage = get_job_storage()
        jobs_data = job_storage.list_jobs(drama_id=self.id)

        return [
            Job(
                jobId=job_data["job_id"],
                dramaId=job_data.get("drama_id", ""),
                assetId=job_data.get("asset_id"),
                type=job_data.get("type", job_data.get("job_type", "unknown")),
                status=job_data["status"],
                prompt=job_data.get("prompt"),
                r2Url=job_data.get("r2_url"),
                createdAt=job_data["created_at"],
                startedAt=job_data.get("started_at"),
                completedAt=job_data.get("completed_at"),
                error=job_data.get("error"),
                parentJobId=job_data.get("parent_job_id"),
                childJobs=job_data.get("child_jobs"),
                totalJobs=job_data.get("total_jobs"),
                completedJobs=job_data.get("completed_jobs"),
                failedJobs=job_data.get("failed_jobs"),
                runningJobs=job_data.get("running_jobs"),
            )
            for job_data in jobs_data
        ]


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
                    _drama_id=drama_pydantic.id,
                )
                for char in drama_pydantic.characters
            ],
            episodes=[
                Episode(
                    id=ep.id,
                    title=ep.title,
                    description=ep.description,
                    url=ep.url,
                    _drama_id=drama_pydantic.id,
                    scenes=[
                        Scene(
                            id=scene.id,
                            description=scene.description,
                            imageUrl=scene.image_url,
                            videoUrl=scene.video_url,
                            _drama_id=drama_pydantic.id,
                            _episode_id=ep.id,
                        )
                        for scene in ep.scenes
                    ],
                )
                for ep in drama_pydantic.episodes
            ],
        )

    @strawberry.field
    async def drama_summaries(self, limit: int = 100) -> List[DramaSummary]:
        """Get drama summaries from index (fast, lightweight)"""
        summaries, _ = await storage.list_drama_summaries(limit=limit)

        return [
            DramaSummary(
                id=summary["id"],
                title=summary["title"],
                description=summary["description"],
                premise=summary["premise"],
                url=summary.get("url"),
                createdAt=summary["created_at"],
                updatedAt=summary["updated_at"],
            )
            for summary in summaries
        ]

    @strawberry.field
    async def dramas(self, limit: int = 100) -> List[Drama]:
        """Get all dramas with full details (slower, fetches from R2)"""
        drama_list, _ = await storage.list_dramas(limit=limit)

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

    @strawberry.field
    async def job(self, id: str) -> Optional[Job]:
        """Get job status by job ID"""
        job_storage = get_job_storage()
        job_data = job_storage.get_job(id)

        if not job_data:
            return None

        return Job(
            jobId=job_data["job_id"],
            dramaId=job_data.get("drama_id", ""),
            assetId=job_data.get("asset_id"),
            type=job_data.get("type", job_data.get("job_type", "unknown")),
            status=job_data["status"],
            prompt=job_data.get("prompt"),
            r2Url=job_data.get("r2_url"),
            createdAt=job_data["created_at"],
            startedAt=job_data.get("started_at"),
            completedAt=job_data.get("completed_at"),
            error=job_data.get("error"),
            parentJobId=job_data.get("parent_job_id"),
            childJobs=job_data.get("child_jobs"),
            totalJobs=job_data.get("total_jobs"),
            completedJobs=job_data.get("completed_jobs"),
            failedJobs=job_data.get("failed_jobs"),
            runningJobs=job_data.get("running_jobs"),
        )

    @strawberry.field
    async def jobs(self, drama_id: str, status: Optional[str] = None) -> List[Job]:
        """Get all jobs for a drama, optionally filtered by status"""
        job_storage = get_job_storage()
        jobs_data = job_storage.list_jobs(drama_id=drama_id, status=status)

        return [
            Job(
                jobId=job_data["job_id"],
                dramaId=job_data.get("drama_id", ""),
                assetId=job_data.get("asset_id"),
                type=job_data.get("type", job_data.get("job_type", "unknown")),
                status=job_data["status"],
                prompt=job_data.get("prompt"),
                r2Url=job_data.get("r2_url"),
                createdAt=job_data["created_at"],
                startedAt=job_data.get("started_at"),
                completedAt=job_data.get("completed_at"),
                error=job_data.get("error"),
                parentJobId=job_data.get("parent_job_id"),
                childJobs=job_data.get("child_jobs"),
                totalJobs=job_data.get("total_jobs"),
                completedJobs=job_data.get("completed_jobs"),
                failedJobs=job_data.get("failed_jobs"),
                runningJobs=job_data.get("running_jobs"),
            )
            for job_data in jobs_data
        ]


# Mutation type
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def generate_character_image(self, drama_id: str, character_id: str) -> Optional[Character]:
        """Generate image for a character (creates a job and generates synchronously)"""
        drama_pydantic = await storage.get_drama(drama_id)
        if not drama_pydantic:
            return None

        # Find character
        character = next((c for c in drama_pydantic.characters if c.id == character_id), None)
        if not character:
            return None

        # Create job for tracking
        job_storage = get_job_storage()
        job = job_storage.create_job(
            drama_id=drama_id,
            asset_id=character_id,
            job_type="image",
            prompt=character.description,
            metadata={
                "character_id": character_id,
                "name": character.name,
                "type": "character_portrait"
            }
        )

        # Update job to running
        job_storage.update_job(job["job_id"], {"status": "running"})

        try:
            # Generate image
            ai_service = get_ai_service()
            image_url = await ai_service.generate_character_image(
                drama_id=drama_id,
                character=character,
            )

            # Update character
            character.url = image_url
            await storage.save_drama(drama_pydantic)

            # Update job to completed
            job_storage.update_job(job["job_id"], {
                "status": "completed",
                "r2_url": image_url,
                "completed_at": datetime.utcnow().isoformat()
            })

        except Exception as e:
            # Update job to failed
            job_storage.update_job(job["job_id"], {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow().isoformat()
            })
            raise

        return Character(
            id=character.id,
            name=character.name,
            description=character.description,
            gender=character.gender,
            voice_description=character.voice_description,
            main=character.main,
            url=character.url,
            _drama_id=drama_id,
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
                    _drama_id=drama_pydantic.id,
                )
                for char in drama_pydantic.characters
            ],
            episodes=[
                Episode(
                    id=ep.id,
                    title=ep.title,
                    description=ep.description,
                    url=ep.url,
                    _drama_id=drama_pydantic.id,
                    scenes=[
                        Scene(
                            id=scene.id,
                            description=scene.description,
                            imageUrl=scene.image_url,
                            videoUrl=scene.video_url,
                            _drama_id=drama_pydantic.id,
                            _episode_id=ep.id,
                        )
                        for scene in ep.scenes
                    ],
                )
                for ep in drama_pydantic.episodes
            ],
        )


# Create schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
