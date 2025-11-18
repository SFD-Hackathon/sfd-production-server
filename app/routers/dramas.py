"""Drama management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from typing import Union
import time
import random
import string

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

        # Update job status to completed
        job_manager.update_job_status(job_id, JobStatus.completed, result={"dramaId": drama_id})

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
