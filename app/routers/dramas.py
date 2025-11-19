"""Drama management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Response, File, UploadFile, Form, Request
from typing import Union, Optional
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
    CriticDramaRequest,
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


async def process_drama_generation(job_id: str, drama_id: str, premise: str, model: str = "gemini-3-pro-preview", reference_image_url: Optional[str] = None):
    """Background task for drama generation

    Args:
        job_id: Job ID for tracking
        drama_id: Drama ID
        premise: Text premise for generation
        model: AI model to use ('gpt-5.1' or 'gemini-3-pro-preview')
        reference_image_url: Optional URL to reference image for character generation
    """
    try:
        # Update job status to processing
        job_manager.update_job_status(job_id, JobStatus.processing)

        # Get initial hash to detect conflicts during entire job execution
        initial_hash = await storage.get_current_hash_from_id(drama_id)

        # Generate drama using AI
        ai_service = get_ai_service()
        drama = await ai_service.generate_drama(premise, drama_id, model)

        # If reference image URL provided, store it in drama metadata
        if reference_image_url:
            if not drama.metadata:
                drama.metadata = {}
            drama.metadata['reference_image_url'] = reference_image_url
            print(f"Stored reference image URL in drama metadata: {reference_image_url}")

        # Save to storage with hash verification (protects against drama created during AI generation)
        await storage.save_drama(drama, expected_hash=initial_hash)

        # Compute hash after first save for conflict detection during image generation
        drama_hash = storage._compute_drama_hash(drama)

        # Print initial drama DAG JSON (before image generation)
        drama_json_initial = drama.model_dump_json(indent=2)
        print(f"\n{'='*80}")
        print(f"DRAMA DAG READY (INITIAL): {drama_id}")
        print(f"{'='*80}")
        print(f"Drama DAG JSON (before image generation):")
        print(drama_json_initial)
        print(f"{'='*80}\n")

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

        # Save updated drama with hash verification to detect concurrent modifications
        await storage.save_drama(drama, expected_hash=drama_hash)

        # Print drama DAG JSON
        drama_json = drama.model_dump_json(indent=2)
        print(f"\n{'='*80}")
        print(f"DRAMA CREATION COMPLETED: {drama_id}")
        print(f"{'='*80}")
        print(f"Drama DAG JSON:")
        print(drama_json)
        print(f"{'='*80}\n")

        # Update job status to completed
        job_manager.update_job_status(job_id, JobStatus.completed, result={"dramaId": drama_id})

    except Exception as e:
        # Update job status to failed
        job_manager.update_job_status(job_id, JobStatus.failed, error=str(e))


async def process_drama_improvement(job_id: str, original_id: str, improved_id: str, feedback: str, model: str = "gemini-3-pro-preview"):
    """Background task for drama improvement"""
    try:
        # Update job status to processing
        job_manager.update_job_status(job_id, JobStatus.processing)

        # Get initial hash to detect conflicts during entire job execution
        initial_hash = await storage.get_current_hash_from_id(improved_id)

        # Get original drama
        original_drama = await storage.get_drama(original_id)
        if not original_drama:
            raise Exception(f"Original drama {original_id} not found")

        # Improve drama using AI
        ai_service = get_ai_service()
        improved_drama = await ai_service.improve_drama(original_drama, feedback, improved_id, model)

        # Save to storage with hash verification (protects against drama created during AI generation)
        await storage.save_drama(improved_drama, expected_hash=initial_hash)

        # Compute hash after first save for conflict detection during image generation
        drama_hash = storage._compute_drama_hash(improved_drama)

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

        # Save updated drama with hash verification to detect concurrent modifications
        await storage.save_drama(improved_drama, expected_hash=drama_hash)

        # Update job status to completed
        job_manager.update_job_status(job_id, JobStatus.completed, result={"dramaId": improved_id})

    except Exception as e:
        # Update job status to failed
        job_manager.update_job_status(job_id, JobStatus.failed, error=str(e))


async def process_drama_critique(job_id: str, drama_id: str, model: str = "gemini-3-pro-preview"):
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
        feedback = await ai_service.critique_drama(drama, model)

        # Update job status to completed with feedback in result
        job_manager.update_job_status(job_id, JobStatus.completed, result={"feedback": feedback})

    except Exception as e:
        # Update job status to failed
        job_manager.update_job_status(job_id, JobStatus.failed, error=str(e))


@router.post("", response_model=Union[Drama, JobResponse])
async def create_drama(
    request: Request,
    background_tasks: BackgroundTasks,
    response: Response,
):
    """
    Create a new drama (supports three modes).

    **Mode 1 (Async - JSON)**: Send JSON with "premise" field → AI generates drama + character images + cover image → Returns job ID (202)
    **Mode 2 (Async - Multipart)**: Send form data with "premise" + optional "reference_image" file → AI generates drama using reference → Returns job ID (202)
    **Mode 3 (Sync)**: Send JSON with "drama" field → Saves drama as-is → Returns drama object (201)

    Mode 1 & 2 generate: ✅ Drama structure, ✅ Character portraits, ✅ Cover image
    Mode 1 & 2 do NOT generate: ❌ Scene assets (use POST /dramas/{id}/generate)

    **AI Model Selection (Mode 1 & 2):**
    - **Default**: `gemini-3-pro-preview` (Google Gemini 3 Pro Preview) - High-quality, fast, cost-effective
    - **Alternative**: `gpt-5.1` (OpenAI GPT-5.1) - Available for comparison
    - Specify using `"model"` field in JSON or form data
    - If not specified, defaults to Gemini 3 Pro Preview
    """
    content_type = request.headers.get("content-type", "")

    # Mode 2: Multipart/form-data (with optional reference image)
    if "multipart/form-data" in content_type:
        form = await request.form()
        premise = form.get("premise")
        drama_id = form.get("id") or generate_id("drama")
        model = form.get("model") or "gemini-3-pro-preview"
        reference_image = form.get("reference_image")

        if not premise:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'premise' is required in multipart request"
            )

        job_id = generate_id("job")

        # Save reference image if provided
        reference_image_url = None
        if reference_image and hasattr(reference_image, 'filename') and reference_image.filename:
            from app.asset_library import AssetLibrary

            # Read file content
            file_content = await reference_image.read()

            # Upload to R2
            lib = AssetLibrary(user_id="10000", project_name=drama_id)
            asset_metadata = lib.upload_asset(
                content=file_content,
                asset_type="image",
                tag="character",
                filename=reference_image.filename,
                metadata={
                    'drama_id': drama_id,
                    'source': 'reference_image',
                    'type': 'character_reference'
                }
            )
            reference_image_url = asset_metadata.get('public_url')
            print(f"✓ Uploaded reference image: {reference_image_url}")

        # Create job
        job_manager.create_job(job_id, drama_id, JobType.generate_drama)

        # Queue background task with model and reference image URL
        background_tasks.add_task(
            process_drama_generation,
            job_id,
            drama_id,
            premise,
            model,
            reference_image_url
        )

        # Set response status to 202 Accepted
        response.status_code = status.HTTP_202_ACCEPTED

        return JobResponse(
            dramaId=drama_id,
            jobId=job_id,
            status=JobStatus.pending,
            message=f"Drama generation job queued. Check status at: https://api.shortformdramas.com/dramas/{drama_id}/jobs/{job_id}",
        )

    # Mode 1 & 3: JSON request
    else:
        try:
            body = await request.json()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON body: {str(e)}"
            )

        # Mode 1: Async - JSON with premise
        if "premise" in body:
            premise = body["premise"]
            drama_id = body.get("id") or generate_id("drama")
            model = body.get("model") or "gemini-3-pro-preview"
            job_id = generate_id("job")

            # Create job
            job_manager.create_job(job_id, drama_id, JobType.generate_drama)

            # Queue background task with model (no reference image for JSON mode)
            background_tasks.add_task(
                process_drama_generation,
                job_id,
                drama_id,
                premise,
                model,
                None  # No reference image
            )

            # Set response status to 202 Accepted
            response.status_code = status.HTTP_202_ACCEPTED

            return JobResponse(
                dramaId=drama_id,
                jobId=job_id,
                status=JobStatus.pending,
                message=f"Drama generation job queued. Check status at: https://api.shortformdramas.com/dramas/{drama_id}/jobs/{job_id}",
            )

        # Mode 3: Sync - JSON with complete drama
        elif "drama" in body:
            drama = Drama(**body["drama"])
            response.status_code = status.HTTP_201_CREATED
            await storage.save_drama(drama)
            return drama

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either 'premise' (async mode) or 'drama' (sync mode)"
            )


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
    The selected AI model will regenerate the drama incorporating your feedback.
    Creates a new improved version with a new ID.

    **AI Model Selection:**
    - **Default**: `gemini-3-pro-preview` (Google Gemini 3 Pro Preview)
    - **Alternative**: `gpt-5.1` (OpenAI GPT-5.1)
    - Specify using `"model"` field in request body
    - If not specified, defaults to Gemini 3 Pro Preview
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

    # Queue background task with model parameter
    background_tasks.add_task(process_drama_improvement, job_id, drama_id, improved_id, request.feedback, request.model)

    # Return response
    return ImproveDramaResponse(
        originalId=drama_id,
        improvedId=improved_id,
        jobId=job_id,
        status=JobStatus.pending,
        message=f"Drama improvement job queued. Check status at: https://api.shortformdramas.com/dramas/{improved_id}/jobs/{job_id}",
    )


@router.post("/{drama_id}/generate", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_drama_assets(drama_id: str, background_tasks: BackgroundTasks):
    """
    Generate all scene and episode assets for a drama (excludes character assets).

    Returns job ID immediately. Character images must already exist (from POST /dramas).
    Generates scene storyboards and video clips using hierarchical DAG execution.
    Poll job status: GET /dramas/{dramaId}/jobs/{jobId}
    """
    # Check if drama exists
    exists = await storage.drama_exists(drama_id)
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Drama not found", "message": f"Drama {drama_id} not found"},
        )

    # Generate job ID for the parent DAG job
    job_id = generate_id("job")

    # Create a placeholder job (will be replaced by DAG executor's parent job)
    job_manager.create_job(job_id, drama_id, JobType.generate_drama)

    # Queue background task for DAG execution
    async def execute_dag_background():
        try:
            from app.hierarchical_dag_engine import HierarchicalDAGExecutor, NodeType
            import logging

            logger = logging.getLogger(__name__)

            # Get drama
            drama = await storage.get_drama(drama_id)
            if not drama:
                raise Exception(f"Drama {drama_id} not found")

            # Create executor and build full DAG
            executor = HierarchicalDAGExecutor(
                drama=drama,
                user_id="10000",
                project_name=drama_id
            )

            # Build full hierarchical DAG
            dag = executor.build_hierarchical_dag()

            # Filter to only episode branch (episodes, scenes, scene_assets)
            # Exclude character branch (characters, character_assets)
            filtered_nodes = {
                node_id: node
                for node_id, node in executor.nodes.items()
                if node.node_type in NodeType.EPISODE_BRANCH
            }

            # Update executor with filtered nodes
            executor.nodes = filtered_nodes

            # Filter DAG dependencies to only include nodes that exist
            filtered_dag = {
                node_id: [dep for dep in deps if dep in filtered_nodes]
                for node_id, deps in dag.items()
                if node_id in filtered_nodes
            }

            logger.info(f"Filtered DAG to {len(filtered_nodes)} episode-related nodes")

            # Print initial drama DAG JSON (before asset generation)
            initial_drama = await storage.get_drama(drama_id)
            if initial_drama:
                drama_json_initial = initial_drama.model_dump_json(indent=2)
                print(f"\n{'='*80}")
                print(f"DRAMA DAG READY (INITIAL): {drama_id}")
                print(f"{'='*80}")
                print(f"Drama DAG JSON (before asset generation):")
                print(drama_json_initial)
                print(f"{'='*80}\n")

            # Execute filtered DAG manually (don't call execute_dag which rebuilds)
            # Get execution order
            levels = executor.topological_sort(filtered_dag)

            # Get or create jobs
            executor.get_or_create_jobs(resume=False)

            # Track dependency results
            dependency_results = {}

            # Execute level by level
            for level_index, level_node_ids in enumerate(levels):
                logger.info(f"Executing level {level_index}: {len(level_node_ids)} nodes")

                # Get nodes for this level
                level_nodes = [executor.nodes[node_id] for node_id in level_node_ids]

                # Execute level in parallel
                level_results = executor.execute_level(level_nodes, dependency_results)

            # Get final status
            result = executor.get_execution_status()

            # Print drama DAG JSON after generation completes
            updated_drama = await storage.get_drama(drama_id)
            if updated_drama:
                drama_json = updated_drama.model_dump_json(indent=2)
                print(f"\n{'='*80}")
                print(f"DRAMA GENERATION COMPLETED: {drama_id}")
                print(f"{'='*80}")
                print(f"Drama DAG JSON:")
                print(drama_json)
                print(f"{'='*80}\n")

            # Update job with results
            if result["status"] == "completed":
                job_manager.update_job_status(job_id, JobStatus.completed, result=result)
            else:
                # Extract error information from failed jobs
                failed_jobs = [j for j in result.get("jobs", []) if j.get("status") == "failed"]
                error_messages = [f"{j.get('asset_id', 'unknown')}: {j.get('error', 'Unknown error')}" for j in failed_jobs]
                error_summary = f"{result['failed_jobs']}/{result['total_jobs']} jobs failed. " + "; ".join(error_messages[:3])
                job_manager.update_job_status(job_id, JobStatus.failed, error=error_summary, result=result)
        except Exception as e:
            job_manager.update_job_status(job_id, JobStatus.failed, error=str(e))

    background_tasks.add_task(execute_dag_background)

    return JobResponse(
        dramaId=drama_id,
        jobId=job_id,
        status=JobStatus.pending,
        message=f"Drama asset generation DAG queued. Check status at: https://api.shortformdramas.com/dramas/{drama_id}/jobs/{job_id}",
    )


@router.post("/{drama_id}/critic", response_model=CriticResponse, status_code=status.HTTP_202_ACCEPTED)
async def critique_drama(
    drama_id: str,
    request: CriticDramaRequest,
    background_tasks: BackgroundTasks,
):
    """
    Get AI-powered critical feedback on a drama script

    Queue an async job to get expert critical analysis of the drama's storytelling,
    character development, pacing, dialogue, and overall narrative quality.

    The critique focuses on:
    - Story structure and pacing
    - Character development and consistency
    - Dialogue quality and authenticity
    - Emotional impact and engagement
    - Scene composition and flow
    - Overall narrative coherence

    **AI Model Selection:**
    - **Default**: `gemini-3-pro-preview` (Google Gemini 3 Pro Preview) - High-quality critique analysis
    - **Alternative**: `gpt-5.1` (OpenAI GPT-5.1)
    - Specify using `"model"` field in request body
    - If not specified, defaults to Gemini 3 Pro Preview

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

    # Queue background task with model parameter
    background_tasks.add_task(process_drama_critique, job_id, drama_id, request.model)

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

        # Note: Character image is optional - if present, it can be used as reference
        # If not present, video will be generated from character description alone
        if not character.url:
            print(f"⚠️  Character {character_id} does not have an image. Generating video from description only.")

        # Generate audition video (modifies character.assets in-place)
        ai_service = get_ai_service()
        video_url = await ai_service.generate_character_audition_video(
            drama_id=drama_id,
            character=character,
        )

        # Find the video asset that was just created
        video_asset = None
        for asset in character.assets:
            if asset.kind == AssetKind.video and asset.metadata and asset.metadata.get("type") == "character_audition":
                video_asset = asset
                break

        if not video_asset:
            raise Exception("Video asset was not created")

        # Safely add asset using storage method (prevents lost updates)
        await storage.add_asset_to_character(drama_id, character_id, video_asset)

        # Log generation success with paths
        local_path = video_asset.url if hasattr(video_asset, 'url') and video_asset.url else "N/A"
        print(f"✓ Video generation completed for {character.name}. local_path: {local_path}, public_url: {video_url}")

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
    If the character has an image, it will be used as a reference for the video.
    Otherwise, the video will be generated from the character description.

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

    # Note: Character image is optional - if present, it will be used as reference

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


@router.get("/{drama_id}/cover_photo")
async def get_cover_photo(drama_id: str):
    """
    Get drama cover photo URL

    **Returns:**
    - JSON with cover photo URL if it exists
    - 404 if drama not found
    - 404 if cover photo not generated yet

    **Example:**
    ```
    GET /dramas/drama_123/cover_photo

    Response:
    {
      "url": "https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/dramas/drama_123/cover.png"
    }
    ```
    """
    # Get drama
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drama {drama_id} not found"
        )

    # Check if cover photo exists
    if not drama.url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cover photo not generated yet. Call POST /dramas/{drama_id}/cover_photo to generate it."
        )

    return {"url": drama.url}


@router.post("/{drama_id}/cover_photo", response_model=Drama)
async def generate_cover_photo(drama_id: str):
    """
    Generate drama cover photo featuring main characters

    **Prerequisites:**
    - All main characters must have images generated first
    - Call POST /dramas/{drama_id}/characters/{character_id}/generate for each main character

    **Process:**
    1. Fetches the drama and validates all main characters have images
    2. Generates a cover image featuring the main characters
    3. Uploads to R2 storage
    4. Updates drama.url with the cover photo URL

    **Returns:**
    - Updated Drama object with cover photo URL in the `url` field

    **Example:**
    ```
    POST /dramas/drama_123/cover_photo
    ```
    """
    # Get drama
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drama {drama_id} not found"
        )

    # Check that all main characters have images
    main_characters = [char for char in drama.characters if char.main]
    if not main_characters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Drama must have at least one main character"
        )

    characters_without_images = [char.name for char in main_characters if not char.url]
    if characters_without_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All main characters must have images generated first. Missing images for: {', '.join(characters_without_images)}"
        )

    # Generate cover image
    ai_service = get_ai_service()
    try:
        cover_url = await ai_service.generate_drama_cover_image(
            drama_id=drama_id,
            drama=drama,
        )

        # Update drama with cover URL
        drama.url = cover_url
        await storage.save_drama(drama)

        return drama

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate cover photo: {str(e)}"
        )
