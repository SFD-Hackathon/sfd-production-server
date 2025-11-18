"""Drama management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from typing import Union
import time
import random
import string
import asyncio

from app.models import (
    Drama,
    CreateFromPremise,
    CreateFromJSON,
    DramaUpdate,
    JobResponse,
    DramaListResponse,
    ImproveDramaRequest,
    ImproveDramaResponse,
    CriticResponse,
    JobType,
    JobStatus,
    Asset,
    AssetKind,
)
from app.storage import storage
from app.ai_service import get_ai_service
from app.job_manager import job_manager

router = APIRouter()


def generate_id(prefix: str = "drama") -> str:
    """Generate a random ID"""
    random_part = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"{prefix}_{random_part}"


async def process_drama_generation(job_id: str, drama_id: str, premise: str):
    """Background task for drama generation"""
    try:
        # Update job status to processing
        job_manager.update_job_status(job_id, JobStatus.processing)

        # Generate drama using AI
        ai_service = get_ai_service()
        drama = await ai_service.generate_drama(premise, drama_id)

        # Save to storage
        await storage.save_drama(drama)

        # Generate character images for all characters in parallel
        async def generate_char_image(character):
            try:
                # Generate image asynchronously
                image_url = await ai_service.generate_character_image(
                    drama_id=drama_id,
                    character=character,
                )
                character.url = image_url
                print(f"✓ Generated image for character: {character.name}")
            except Exception as char_error:
                print(f"Warning: Failed to generate image for character {character.id}: {char_error}")

        # Generate all character images concurrently
        await asyncio.gather(*[generate_char_image(char) for char in drama.characters])

        # Generate drama cover image featuring main characters
        try:
            cover_url = await ai_service.generate_drama_cover_image(
                drama_id=drama_id,
                drama=drama,
            )
            # Set drama url to cover image
            drama.url = cover_url
            print(f"✓ Generated drama cover image")
        except Exception as cover_error:
            print(f"Warning: Failed to generate drama cover image: {cover_error}")

        # Save updated drama with character images and cover
        await storage.save_drama(drama)

        # Update job status to completed
        job_manager.update_job_status(job_id, JobStatus.completed, result={"dramaId": drama_id})

        # Create separate jobs for each character's audition video (non-blocking)
        video_job_ids = []
        for character in drama.characters:
            if character.url:  # Only create job if character has image
                video_job_id = generate_id("job")
                job_manager.create_job(video_job_id, drama_id, JobType.generate_video)
                video_job_ids.append(video_job_id)

                # Queue each character video as a separate background task
                asyncio.create_task(process_character_audition_video(video_job_id, drama_id, character.id))

        print(f"✓ Queued {len(video_job_ids)} character audition video jobs")

    except Exception as e:
        # Update job status to failed
        job_manager.update_job_status(job_id, JobStatus.failed, error=str(e))


async def process_drama_improvement(job_id: str, original_id: str, improved_id: str, feedback: str):
    """Background task for drama improvement"""
    try:
        # Update job status to processing
        job_manager.update_job_status(job_id, JobStatus.processing)

        # Get original drama
        original_drama = await storage.get_drama(original_id)
        if not original_drama:
            raise Exception(f"Original drama {original_id} not found")

        # Improve drama using AI
        ai_service = get_ai_service()
        improved_drama = await ai_service.improve_drama(original_drama, feedback, improved_id)

        # Save to storage
        await storage.save_drama(improved_drama)

        # Generate character images for characters without URLs in parallel
        async def generate_char_image(character):
            if not character.url:  # Only generate if character doesn't have an image
                try:
                    # Generate image asynchronously
                    image_url = await ai_service.generate_character_image(
                        drama_id=improved_id,
                        character=character,
                    )
                    character.url = image_url
                    print(f"✓ Generated image for character: {character.name}")
                except Exception as char_error:
                    print(f"Warning: Failed to generate image for character {character.id}: {char_error}")

        # Generate all character images concurrently
        await asyncio.gather(*[generate_char_image(char) for char in improved_drama.characters])

        # Generate drama cover image featuring main characters
        try:
            cover_url = await ai_service.generate_drama_cover_image(
                drama_id=improved_id,
                drama=improved_drama,
            )
            # Set drama url to cover image
            improved_drama.url = cover_url
            print(f"✓ Generated drama cover image")
        except Exception as cover_error:
            print(f"Warning: Failed to generate drama cover image: {cover_error}")

        # Save updated drama with character images and cover
        await storage.save_drama(improved_drama)

        # Update job status to completed
        job_manager.update_job_status(job_id, JobStatus.completed, result={"dramaId": improved_id})

    except Exception as e:
        # Update job status to failed
        job_manager.update_job_status(job_id, JobStatus.failed, error=str(e))


async def process_drama_critique(job_id: str, drama_id: str):
    """Background task for drama critique"""
    try:
        # Update job status to processing
        job_manager.update_job_status(job_id, JobStatus.processing)

        # Get drama
        drama = await storage.get_drama(drama_id)
        if not drama:
            raise Exception(f"Drama {drama_id} not found")

        # Get critique from AI
        ai_service = get_ai_service()
        feedback = await ai_service.critique_drama(drama)

        # Update job status to completed with feedback in result
        job_manager.update_job_status(job_id, JobStatus.completed, result={"feedback": feedback})

    except Exception as e:
        # Update job status to failed
        job_manager.update_job_status(job_id, JobStatus.failed, error=str(e))


@router.post("", response_model=Union[Drama, JobResponse], status_code=status.HTTP_201_CREATED)
async def create_drama(
    request: Union[CreateFromPremise, CreateFromJSON],
    background_tasks: BackgroundTasks,
):
    """
    Create a new drama

    Create a drama from either a text premise (async, queued for AI generation)
    or a complete JSON object (sync).

    **Async Mode (from premise):**
    - Returns immediately with 202 Accepted
    - Job is queued for GPT-5 generation (30-60 seconds)
    - Use GET /dramas/{id}/jobs/{jobId} to check status

    **Sync Mode (from JSON):**
    - Returns immediately with 201 Created
    - Drama is stored directly without AI generation
    """
    # Check if this is premise-based (async) or JSON-based (sync)
    if isinstance(request, CreateFromPremise) or hasattr(request, "premise"):
        # Async mode - generate from premise
        drama_id = request.id if hasattr(request, "id") and request.id else generate_id("drama")
        job_id = generate_id("job")

        # Create job
        job_manager.create_job(job_id, drama_id, JobType.generate_drama)

        # Queue background task
        background_tasks.add_task(process_drama_generation, job_id, drama_id, request.premise)

        # Return 202 Accepted with job info
        return JobResponse(
            dramaId=drama_id,
            jobId=job_id,
            status=JobStatus.pending,
            message=f"Drama generation job queued. Check status at: https://api.shortformdramas.com/dramas/{drama_id}/jobs/{job_id}",
        )
    else:
        # Sync mode - save provided drama
        drama = request.drama
        await storage.save_drama(drama)
        return drama


@router.get("", response_model=DramaListResponse)
async def list_dramas(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of dramas to return"),
    cursor: str = Query(default=None, description="Pagination cursor from previous response"),
):
    """
    List all dramas (summary view)

    Retrieve a paginated list of all dramas with only top-level fields.
    Use GET /dramas/{dramaId} to get full details including characters, episodes, and scenes.
    """
    dramas, next_cursor = await storage.list_dramas(limit=limit, cursor=cursor)

    # Convert to summary view (exclude characters, episodes, assets)
    drama_summaries = [
        {
            "id": drama.id,
            "title": drama.title,
            "description": drama.description,
            "premise": drama.premise,
            "url": drama.url,
            "metadata": drama.metadata,
        }
        for drama in dramas
    ]

    return DramaListResponse(dramas=drama_summaries, cursor=next_cursor)


@router.get("/{drama_id}", response_model=Drama)
async def get_drama(drama_id: str):
    """
    Get a specific drama

    Retrieve complete details of a single drama
    """
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )
    return drama


@router.patch("/{drama_id}", response_model=Drama)
async def update_drama(drama_id: str, update: DramaUpdate):
    """
    Update a drama

    Partially update drama properties
    """
    # Get existing drama
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(drama, field, value)

    # Save updated drama
    await storage.save_drama(drama)
    return drama


@router.delete("/{drama_id}")
async def delete_drama(drama_id: str):
    """
    Delete a drama

    Permanently delete a drama and all its associated data
    """
    success = await storage.delete_drama(drama_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )
    return {"success": True}


@router.post("/{drama_id}/improve", response_model=ImproveDramaResponse, status_code=status.HTTP_202_ACCEPTED)
async def improve_drama(
    drama_id: str,
    request: ImproveDramaRequest,
    background_tasks: BackgroundTasks,
):
    """
    Improve drama with feedback

    Queue an async job to improve an existing drama based on feedback.
    GPT-5 will regenerate the drama incorporating your feedback.
    Creates a new improved version with a new ID.
    """
    # Check if original drama exists
    exists = await storage.drama_exists(drama_id)
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    # Generate IDs
    improved_id = request.newDramaId if request.newDramaId else f"{drama_id}_improved_{int(time.time() * 1000)}"
    job_id = generate_id("job")

    # Create job
    job_manager.create_job(job_id, improved_id, JobType.improve_drama)

    # Queue background task
    background_tasks.add_task(process_drama_improvement, job_id, drama_id, improved_id, request.feedback)

    # Return response
    return ImproveDramaResponse(
        originalId=drama_id,
        improvedId=improved_id,
        jobId=job_id,
        status=JobStatus.pending,
        message=f"Drama improvement job queued. Check status at: https://api.shortformdramas.com/dramas/{improved_id}/jobs/{job_id}",
    )


@router.post("/{drama_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_drama_assets(drama_id: str):
    """
    Generate all assets for a drama

    Triggers asset generation jobs for all assets in the drama hierarchy
    (drama assets, character assets, episode assets, scene assets).

    **Status:** Not implemented yet - placeholder for future asset generation
    """
    # TODO: Implement asset generation logic
    # This will:
    # 1. Traverse all assets in the drama
    # 2. For each asset without a URL, create a generation job
    # 3. Queue jobs for image/video generation
    # 4. Return list of created job IDs

    return {
        "message": "Asset generation not implemented yet",
        "dramaId": drama_id,
        "status": "not_implemented"
    }


@router.post("/{drama_id}/critic", response_model=CriticResponse, status_code=status.HTTP_202_ACCEPTED)
async def critique_drama(
    drama_id: str,
    background_tasks: BackgroundTasks,
):
    """
    Get AI-powered critical feedback on a drama script

    Queue an async job to get expert critical analysis of the drama's storytelling,
    character development, pacing, dialogue, and overall narrative quality.
    GPT-5 will provide actionable feedback to help improve the script.

    The critique focuses on:
    - Story structure and pacing
    - Character development and consistency
    - Dialogue quality and authenticity
    - Emotional impact and engagement
    - Scene composition and flow
    - Overall narrative coherence

    Returns immediately with a job ID. Use the job status endpoint to retrieve
    the critique feedback once the job completes.
    """
    # Check if drama exists
    exists = await storage.drama_exists(drama_id)
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    # Generate job ID
    job_id = generate_id("job")

    # Create job
    job_manager.create_job(job_id, drama_id, JobType.critique_drama)

    # Queue background task
    background_tasks.add_task(process_drama_critique, job_id, drama_id)

    # Return response
    return CriticResponse(
        dramaId=drama_id,
        jobId=job_id,
        status=JobStatus.pending,
        message=f"Drama critique job queued. Check status and retrieve feedback at: https://api.shortformdramas.com/dramas/{drama_id}/jobs/{job_id}",
    )


async def process_character_audition_video(job_id: str, drama_id: str, character_id: str):
    """Background task for generating a single character audition video"""
    try:
        # Update job status to processing
        job_manager.update_job_status(job_id, JobStatus.processing)

        # Get drama and find character
        drama = await storage.get_drama(drama_id)
        if not drama:
            raise Exception(f"Drama {drama_id} not found")

        # Find character
        character = None
        for char in drama.characters:
            if char.id == character_id:
                character = char
                break

        if not character:
            raise Exception(f"Character {character_id} not found in drama {drama_id}")

        # Check if character has image
        if not character.url:
            raise Exception(f"Character {character_id} does not have an image. Generate character image first.")

        # Generate audition video
        ai_service = get_ai_service()

        # Build video asset before generation
        duration = 10
        audition_prompt = f"Character audition video for {character.name}: {character.description}. Voice: {character.voice_description}. Show the character in a dynamic pose, turning slightly and making expressive gestures that showcase their personality and vocal style. Anime style, smooth animation."

        # Generate video and get URL
        video_url = await ai_service.generate_character_audition_video(
            drama_id=drama_id,
            character=character,
        )

        # Find the video asset that was created
        video_asset = None
        for asset in character.assets:
            if asset.kind == AssetKind.video and asset.metadata and asset.metadata.get("type") == "character_audition":
                video_asset = asset
                break

        if not video_asset:
            raise Exception("Video asset was not created by generate_character_audition_video")

        # Atomically add the asset to the character in storage
        await storage.add_character_asset(drama_id, character_id, video_asset)

        # Update job status to completed
        job_manager.update_job_status(
            job_id,
            JobStatus.completed,
            result={"dramaId": drama_id, "characterId": character_id, "videoUrl": video_url}
        )

    except Exception as e:
        # Update job status to failed
        job_manager.update_job_status(job_id, JobStatus.failed, error=str(e))


@router.get("/{drama_id}/characters/{character_id}/audition", response_model=Asset)
async def get_character_audition_video(drama_id: str, character_id: str):
    """
    Get character audition video asset

    Retrieve the audition video asset for a specific character.
    Returns 404 if the character or audition video doesn't exist.
    """
    # Get drama
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    # Find character
    character = None
    for char in drama.characters:
        if char.id == character_id:
            character = char
            break

    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Character not found", "message": f"Character {character_id} not found"},
        )

    # Find audition video asset
    audition_asset = None
    for asset in character.assets:
        if asset.kind == AssetKind.video and asset.metadata and asset.metadata.get("type") == "character_audition":
            audition_asset = asset
            break

    if not audition_asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Audition video not found", "message": f"Audition video for character {character_id} not found"},
        )

    return audition_asset


@router.post("/{drama_id}/characters/{character_id}/audition", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_character_audition_video(
    drama_id: str,
    character_id: str,
    background_tasks: BackgroundTasks,
):
    """
    Generate character audition video

    Queue an async job to generate a 10-second audition video for a specific character.
    The character must have an image already generated (used as reference for the video).

    This endpoint can be used to:
    - Generate audition video for a character that doesn't have one
    - Regenerate audition video for a character (replaces existing video)

    Returns immediately with a job ID. Use the job status endpoint to check completion.
    """
    # Check if drama exists
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    # Find character
    character = None
    for char in drama.characters:
        if char.id == character_id:
            character = char
            break

    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Character not found", "message": f"Character {character_id} not found"},
        )

    # Check if character has image
    if not character.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Character image required", "message": f"Character {character_id} must have an image before generating audition video"},
        )

    # Generate job ID
    job_id = generate_id("job")

    # Create job
    job_manager.create_job(job_id, drama_id, JobType.generate_video)

    # Queue background task
    background_tasks.add_task(process_character_audition_video, job_id, drama_id, character_id)

    # Return response
    return JobResponse(
        dramaId=drama_id,
        jobId=job_id,
        status=JobStatus.pending,
        message=f"Character audition video generation queued. Check status at: https://api.shortformdramas.com/dramas/{drama_id}/jobs/{job_id}",
    )
