"""Base provider interfaces for AI services"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class TextProvider(ABC):
    """Base interface for text generation providers (GPT, Gemini, etc.)"""

    @abstractmethod
    async def generate_structured_output(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel]
    ) -> BaseModel:
        """
        Generate structured output using AI model.

        Args:
            system_prompt: System instructions
            user_prompt: User prompt
            response_schema: Pydantic model class for response validation

        Returns:
            Validated Pydantic model instance
        """
        pass


class ImageProvider(ABC):
    """Base interface for image generation providers"""

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        reference_images: Optional[List[str]] = None
    ) -> bytes:
        """
        Generate an image from prompt.

        Args:
            prompt: Text description of image to generate
            reference_images: Optional list of reference image URLs

        Returns:
            Image bytes
        """
        pass


class VideoProvider(ABC):
    """Base interface for video generation providers"""

    @abstractmethod
    def submit_job(
        self,
        prompt: str,
        duration: int,
        aspect_ratio: str,
        reference_images: Optional[List[str]] = None
    ) -> str:
        """
        Submit a video generation job.

        Args:
            prompt: Text description of video to generate
            duration: Video duration in seconds
            aspect_ratio: Aspect ratio (e.g., "9:16")
            reference_images: Optional list of reference image URLs

        Returns:
            Task/job ID for polling
        """
        pass

    @abstractmethod
    def poll_status(self, task_id: str) -> Dict[str, Any]:
        """
        Poll the status of a video generation job.

        Args:
            task_id: Task ID from submit_job

        Returns:
            Status dict with keys: status, video_url (if completed), error (if failed)
        """
        pass

    @abstractmethod
    def download_video(self, video_url: str, output_path: str) -> str:
        """
        Download video from URL to local file.

        Args:
            video_url: URL of video to download
            output_path: Local path to save video

        Returns:
            Path to downloaded file
        """
        pass
