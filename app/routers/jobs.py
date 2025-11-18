"""Job status tracking endpoints"""

from fastapi import APIRouter, HTTPException, status

from app.models import JobStatusRecord, JobListResponse
from app.job_manager import job_manager

router = APIRouter()


@router.get("/{drama_id}/jobs/{job_id}", response_model=JobStatusRecord)
async def get_job_status(drama_id: str, job_id: str):
    """
    Get job status

    Check the status of a drama generation or improvement job.

    **Status Values:**
    - `pending` - Job queued, waiting to process
    - `processing` - GPT-5 is generating your drama (30-60 seconds)
    - `completed` - Drama ready! Fetch it with GET /dramas/{id}
    - `failed` - Error occurred (check error field)

    **Tip:** Poll this endpoint every 5 seconds until status is completed or failed.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Job not found", "message": f"Job {job_id} not found"},
        )
    return job


@router.get("/{drama_id}/jobs", response_model=JobListResponse)
async def list_drama_jobs(drama_id: str):
    """
    List all jobs for a drama

    Retrieve all generation and improvement jobs associated with a drama
    """
    jobs = job_manager.get_drama_jobs(drama_id)
    return JobListResponse(jobs=jobs)
