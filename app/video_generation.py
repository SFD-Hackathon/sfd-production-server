"""
Sora2 API integration for video generation.

Based on the OpenAI Sora2 API for generating short videos.
"""

import os
import time
import requests
from typing import List, Optional, Dict
from pathlib import Path
import logging

from config import SORA_API_KEY, SORA_API_BASE, DEFAULT_ASPECT_RATIO, OUTPUTS_DIR

logger = logging.getLogger(__name__)


class SoraAPIError(Exception):
    """Sora API error."""
    pass


def submit_video_job(
    prompt: str,
    duration: int = 10,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    reference_images: List[str] = None
) -> str:
    """Submit a video generation job to Sora2 API.

    Args:
        prompt: Generation prompt
        duration: Video duration in seconds (10 or 15)
        aspect_ratio: Aspect ratio (e.g., "9:16")
        reference_images: List of reference image URLs or paths

    Returns:
        Task ID for polling

    Raises:
        SoraAPIError: If API request fails
    """
    if not SORA_API_KEY:
        raise SoraAPIError("SORA_API_KEY not configured")

    url = f"{SORA_API_BASE}/v2/videos/generations"
    headers = {
        "Authorization": f"Bearer {SORA_API_KEY}",
        "Content-Type": "application/json"
    }

    # TODO: Upload reference images to accessible URL if they're local paths
    # For now, we'll pass them as-is if they're URLs
    images = []
    if reference_images:
        for ref in reference_images:
            # If it's a local file, we need to upload it somewhere accessible
            # For MVP, skip local files or implement upload to R2/temp storage
            if ref.startswith("http://") or ref.startswith("https://"):
                images.append(ref)

    payload = {
        "prompt": prompt,
        "model": "sora-2",
        "aspect_ratio": aspect_ratio,
        "duration": str(duration),
        "hd": False
    }

    if images:
        payload["images"] = images

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        task_id = data.get("task_id")
        if not task_id:
            raise SoraAPIError(f"No task_id in response: {data}")

        logger.info(f"Submitted Sora2 job: {task_id}")
        return task_id

    except requests.exceptions.RequestException as e:
        raise SoraAPIError(f"Failed to submit Sora2 job: {e}")


def poll_video_status(task_id: str) -> Dict:
    """Poll the status of a Sora2 video generation job.

    Args:
        task_id: Task ID from submit_video_job

    Returns:
        Status dict with keys: status, video_url (if completed), error (if failed)

    Raises:
        SoraAPIError: If API request fails
    """
    if not SORA_API_KEY:
        raise SoraAPIError("SORA_API_KEY not configured")

    url = f"{SORA_API_BASE}/v2/videos/generations/{task_id}"
    headers = {
        "Authorization": f"Bearer {SORA_API_KEY}"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Map API status to our internal status
        # API returns uppercase with underscores: "IN_PROGRESS", "COMPLETED", "FAILED"
        api_status = data.get("status", "").upper()

        logger.info(f"Sora2 poll response - Task: {task_id}, Status: {api_status}")

        if api_status in ["COMPLETED", "SUCCESS", "DONE"]:
            # Extract video URL from response
            # The URL is in data.output field
            video_url = None
            if "data" in data and isinstance(data["data"], dict):
                video_url = data["data"].get("output")

            # Fallback to other possible locations
            if not video_url:
                video_url = data.get("video_url") or data.get("url") or data.get("output_url")

            if video_url:
                logger.info(f"Sora2 video completed - URL: {video_url}")
            else:
                logger.warning(f"Sora2 video completed but no URL found. Response: {data}")

            return {
                "status": "completed",
                "video_url": video_url,
                "metadata": data
            }
        elif api_status in ["FAILED", "ERROR"]:
            error_msg = data.get("fail_reason") or data.get("error") or data.get("message") or "Unknown error"
            logger.error(f"Sora2 video failed - Task: {task_id}, Error: {error_msg}")
            return {
                "status": "failed",
                "error": error_msg,
                "metadata": data
            }
        elif api_status in ["IN_PROGRESS", "RUNNING", "PROCESSING"]:
            progress = data.get("progress", "unknown")
            logger.debug(f"Sora2 video in progress - Task: {task_id}, Progress: {progress}%")
            return {
                "status": "running",
                "metadata": data
            }
        else:
            # Default to pending for PENDING, QUEUED, WAITING, etc.
            logger.debug(f"Sora2 video pending - Task: {task_id}, Status: {api_status}")
            return {
                "status": "pending",
                "metadata": data
            }

    except requests.exceptions.RequestException as e:
        raise SoraAPIError(f"Failed to poll Sora2 status: {e}")


def download_video(video_url: str, output_path: str) -> str:
    """Download a video from URL to local file.

    Args:
        video_url: URL of the video to download
        output_path: Local path to save the video

    Returns:
        Path to downloaded file

    Raises:
        SoraAPIError: If download fails
    """
    try:
        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Stream download to handle large files
        response = requests.get(video_url, stream=True, timeout=60)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"Downloaded video to {output_path}")
        return output_path

    except requests.exceptions.RequestException as e:
        raise SoraAPIError(f"Failed to download video: {e}")


def generate_video_sora(
    prompt: str,
    drama_id: str,
    asset_id: str,
    duration: int = 10,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    reference_images: List[str] = None,
    max_wait_time: int = 600,
    poll_interval: int = 5
) -> str:
    """Generate a video using Sora2 API and save to local file.

    This is a blocking function that submits the job, polls until completion,
    and downloads the result.

    Args:
        prompt: Generation prompt
        drama_id: Drama identifier
        asset_id: Asset identifier
        duration: Video duration in seconds (10 or 15)
        aspect_ratio: Aspect ratio (e.g., "9:16")
        reference_images: List of reference image URLs or paths
        max_wait_time: Maximum time to wait in seconds (default 600 = 10 minutes)
        poll_interval: Polling interval in seconds (default 5)

    Returns:
        Path to downloaded video file

    Raises:
        SoraAPIError: If generation fails or times out
    """
    # Submit job
    task_id = submit_video_job(prompt, duration, aspect_ratio, reference_images)

    # Poll until completion
    start_time = time.time()
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            raise SoraAPIError(f"Video generation timed out after {max_wait_time}s")

        status = poll_video_status(task_id)

        if status["status"] == "completed":
            video_url = status.get("video_url")
            if not video_url:
                raise SoraAPIError("Video completed but no URL returned")

            # Download to local file
            output_path = os.path.join(OUTPUTS_DIR, drama_id, f"{asset_id}.mp4")
            return download_video(video_url, output_path)

        elif status["status"] == "failed":
            error = status.get("error", "Unknown error")
            raise SoraAPIError(f"Video generation failed: {error}")

        # Still running or pending
        logger.info(f"Sora2 job {task_id} status: {status['status']}, waiting...")
        time.sleep(poll_interval)


async def generate_video_sora_async(
    prompt: str,
    drama_id: str,
    asset_id: str,
    duration: int = 10,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    reference_images: List[str] = None
) -> Dict:
    """Submit a Sora2 video generation job (async, non-blocking).

    This function only submits the job and returns the task ID.
    Use poll_video_status() separately to check status.

    Args:
        prompt: Generation prompt
        drama_id: Drama identifier
        asset_id: Asset identifier
        duration: Video duration in seconds (10 or 15)
        aspect_ratio: Aspect ratio (e.g., "9:16")
        reference_images: List of reference image URLs or paths

    Returns:
        Dict with task_id and initial status
    """
    task_id = submit_video_job(prompt, duration, aspect_ratio, reference_images)

    return {
        "task_id": task_id,
        "status": "pending",
        "drama_id": drama_id,
        "asset_id": asset_id
    }
