"""Sora provider for video generation"""

import os
import time
import requests
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.providers.base import VideoProvider
from app.config import SORA_API_KEY, SORA_API_BASE, DEFAULT_ASPECT_RATIO

logger = logging.getLogger(__name__)


class SoraAPIError(Exception):
    """Sora API error"""
    pass


class SoraProvider(VideoProvider):
    """Sora provider for video generation"""

    def __init__(self):
        """Initialize Sora provider"""
        self.api_key = SORA_API_KEY
        self.api_base = SORA_API_BASE
        self.model = "sora-2"

        if not self.api_key:
            logger.warning("SORA_API_KEY not configured")

    def submit_job(
        self,
        prompt: str,
        duration: int = 10,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        reference_images: Optional[List[str]] = None
    ) -> str:
        """
        Submit a video generation job to Sora API.

        Args:
            prompt: Generation prompt
            duration: Video duration in seconds (10 or 15)
            aspect_ratio: Aspect ratio (e.g., "9:16")
            reference_images: List of reference image URLs

        Returns:
            Task ID for polling

        Raises:
            SoraAPIError: If API request fails
        """
        if not self.api_key:
            raise SoraAPIError("SORA_API_KEY not configured")

        url = f"{self.api_base}/v2/videos/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Filter to only HTTP/HTTPS URLs
        images = []
        if reference_images:
            for ref in reference_images:
                if ref.startswith("http://") or ref.startswith("https://"):
                    images.append(ref)

        payload = {
            "prompt": prompt,
            "model": self.model,
            "aspect_ratio": aspect_ratio,
            "duration": str(duration),
            "hd": False
        }

        if images:
            payload["images"] = images

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            try:
                data = response.json()
            except ValueError as e:
                raise SoraAPIError(
                    f"Failed to parse Sora API response as JSON. "
                    f"Status: {response.status_code}, Content: {response.text[:200]}"
                )

            task_id = data.get("task_id")
            if not task_id:
                raise SoraAPIError(f"No task_id in response: {data}")

            logger.info(f"Submitted Sora job: {task_id}")
            return task_id

        except requests.exceptions.RequestException as e:
            raise SoraAPIError(f"Failed to submit Sora job: {e}")

    def poll_status(self, task_id: str) -> Dict[str, Any]:
        """
        Poll the status of a Sora video generation job.

        Args:
            task_id: Task ID from submit_job

        Returns:
            Status dict with keys: status, video_url (if completed), error (if failed)

        Raises:
            SoraAPIError: If API request fails
        """
        if not self.api_key:
            raise SoraAPIError("SORA_API_KEY not configured")

        url = f"{self.api_base}/v2/videos/generations/{task_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            try:
                data = response.json()
            except ValueError as e:
                raise SoraAPIError(
                    f"Failed to parse Sora API status response as JSON. "
                    f"Status: {response.status_code}, Content: {response.text[:200]}"
                )

            # Map API status to our internal status
            api_status = data.get("status", "").upper()

            logger.info(f"Sora poll response - Task: {task_id}, Status: {api_status}")

            if api_status in ["COMPLETED", "SUCCESS", "DONE"]:
                # Extract video URL from response
                video_url = None
                if "data" in data and isinstance(data["data"], dict):
                    video_url = data["data"].get("output")

                # Fallback to other possible locations
                if not video_url:
                    video_url = data.get("video_url") or data.get("url") or data.get("output_url")

                if video_url:
                    logger.info(f"Sora video completed - URL: {video_url}")
                else:
                    logger.warning(f"Sora video completed but no URL found. Response: {data}")

                return {
                    "status": "completed",
                    "video_url": video_url,
                    "metadata": data
                }
            elif api_status in ["FAILED", "ERROR"]:
                error_msg = (
                    data.get("fail_reason") or
                    data.get("error") or
                    data.get("message") or
                    "Unknown error"
                )
                logger.error(f"Sora video failed - Task: {task_id}, Error: {error_msg}")
                return {
                    "status": "failed",
                    "error": error_msg,
                    "metadata": data
                }
            elif api_status in ["IN_PROGRESS", "RUNNING", "PROCESSING"]:
                progress = data.get("progress", "unknown")
                logger.debug(f"Sora video in progress - Task: {task_id}, Progress: {progress}%")
                return {
                    "status": "running",
                    "metadata": data
                }
            else:
                # Default to pending for PENDING, QUEUED, WAITING, etc.
                logger.debug(f"Sora video pending - Task: {task_id}, Status: {api_status}")
                return {
                    "status": "pending",
                    "metadata": data
                }

        except requests.exceptions.RequestException as e:
            raise SoraAPIError(f"Failed to poll Sora status: {e}")

    def download_video(self, video_url: str, output_path: str) -> str:
        """
        Download a video from URL to local file.

        Args:
            video_url: URL of video to download
            output_path: Local path to save video

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

    def generate_video_blocking(
        self,
        prompt: str,
        output_path: str,
        duration: int = 10,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        reference_images: Optional[List[str]] = None,
        max_wait_time: int = 600,
        poll_interval: int = 5
    ) -> str:
        """
        Generate video with blocking wait (submit, poll, download).

        Args:
            prompt: Generation prompt
            output_path: Local path to save video
            duration: Video duration in seconds (10 or 15)
            aspect_ratio: Aspect ratio (e.g., "9:16")
            reference_images: List of reference image URLs
            max_wait_time: Maximum time to wait in seconds (default 600 = 10 min)
            poll_interval: Polling interval in seconds (default 5)

        Returns:
            Path to downloaded video file

        Raises:
            SoraAPIError: If generation fails or times out
        """
        # Submit job
        task_id = self.submit_job(prompt, duration, aspect_ratio, reference_images)

        # Poll until completion
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                raise SoraAPIError(f"Video generation timed out after {max_wait_time}s")

            status = self.poll_status(task_id)

            if status["status"] == "completed":
                video_url = status.get("video_url")
                if not video_url:
                    raise SoraAPIError("Video completed but no URL returned")

                # Download to local file
                return self.download_video(video_url, output_path)

            elif status["status"] == "failed":
                error = status.get("error", "Unknown error")
                raise SoraAPIError(f"Video generation failed: {error}")

            # Still running or pending
            logger.info(f"Sora job {task_id} status: {status['status']}, waiting...")
            time.sleep(poll_interval)
