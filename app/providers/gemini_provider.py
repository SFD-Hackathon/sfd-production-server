"""Google Gemini provider for text and image generation"""

import os
import re
import base64
import asyncio
import httpx
import logging
from typing import Optional, List
from pydantic import BaseModel
from google import genai
from google.genai import types

from app.providers.base import TextProvider, ImageProvider
from app.config import MAX_RETRIES, NANO_BANANA_API_KEY, NANO_BANANA_API_BASE

logger = logging.getLogger(__name__)


class GeminiProvider(TextProvider, ImageProvider):
    """Google Gemini provider for drama text generation and image generation"""

    def __init__(self):
        """Initialize Gemini clients"""
        # Gemini API for text generation (drama structure)
        self.text_api_key = os.getenv("GEMINI_API_KEY")
        self.text_model = os.getenv("GEMINI_DRAMA_MODEL", "gemini-3-pro-preview")

        if self.text_api_key:
            self.text_client = genai.Client(api_key=self.text_api_key)
        else:
            self.text_client = None

        # Nano Banana API for image generation (uses Gemini image model)
        self.image_api_key = NANO_BANANA_API_KEY
        self.image_api_base = NANO_BANANA_API_BASE
        self.image_model = "gemini-2.5-flash-image"

    # =========================================================================
    # TextProvider Implementation
    # =========================================================================

    async def generate_structured_output(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel]
    ) -> BaseModel:
        """Generate structured output using Gemini"""
        if not self.text_client:
            raise ValueError("Gemini text client not initialized (GEMINI_API_KEY missing)")

        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        response = await asyncio.to_thread(
            lambda: self.text_client.models.generate_content(
                model=self.text_model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    thinking_config=types.ThinkingConfig(thinking_level="low")
                ),
            )
        )

        # Parse JSON response into Pydantic model
        return response_schema.model_validate_json(response.text)

    # =========================================================================
    # ImageProvider Implementation
    # =========================================================================

    async def generate_image(
        self,
        prompt: str,
        reference_images: Optional[List[str]] = None,
        max_retries: Optional[int] = None
    ) -> bytes:
        """
        Generate an image using Gemini image API.

        Args:
            prompt: Text description of image to generate
            reference_images: Optional list of reference image URLs
            max_retries: Number of retry attempts

        Returns:
            Image bytes
        """
        if max_retries is None:
            max_retries = MAX_RETRIES

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await self._generate_image_single_attempt(prompt, reference_images)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    print(f"⚠️  Image generation attempt {attempt + 1} failed: {e}. Retrying...")
                    await asyncio.sleep(2)
                    continue
                else:
                    print(f"❌ Image generation failed after {max_retries + 1} attempts")
                    raise last_error

    async def _generate_image_single_attempt(
        self,
        prompt: str,
        reference_images: Optional[List[str]] = None
    ) -> bytes:
        """Single async attempt to generate image"""
        logger.info(f"[Gemini] Starting image generation attempt...")

        # Build full prompt with vertical format requirement
        full_prompt = (
            "CRITICAL REQUIREMENT: STRICT VERTICAL PORTRAIT FORMAT - 9:16 aspect ratio (1080x1920 pixels). "
            "The image MUST be taller than it is wide. Vertical orientation is MANDATORY.\n\n"
            f"IMAGE CONTENT: {prompt}\n\n"
            "STYLE: Anime style, cartoon illustration, vibrant colors, clean lines."
        )

        # Build request content
        content = [{"type": "text", "text": full_prompt}]

        # Add reference images if provided
        if reference_images:
            logger.info(f"[Gemini] Adding {len(reference_images)} reference images")
            for ref in reference_images:
                content.append({"type": "image_url", "image_url": {"url": ref}})

        # Build API request payload
        payload = {
            "model": self.image_model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.image_api_key}",
            "Content-Type": "application/json",
        }

        # Make async API request
        logger.info(f"[Gemini] Sending request to {self.image_api_base}/v1/chat/completions...")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.image_api_base}/v1/chat/completions",
                headers=headers,
                json=payload
            )

            # Log response status for debugging
            logger.info(f"[Gemini] Received response - Status: {response.status_code}")

            # Check for empty response
            if not response.text or response.text.strip() == "":
                raise Exception(
                    f"Gemini API returned empty response. "
                    f"Status: {response.status_code}, Headers: {dict(response.headers)}"
                )

            response.raise_for_status()

        try:
            result = response.json()
        except ValueError as e:
            raise Exception(
                f"Failed to parse Gemini API response as JSON. "
                f"Status: {response.status_code}, "
                f"Content-Type: {response.headers.get('content-type')}, "
                f"Content: {response.text[:500]}, "
                f"Error: {str(e)}"
            )

        # Extract image from response
        message = result['choices'][0]['message']['content']

        # Check for markdown image URL
        md_match = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', message)
        if md_match:
            image_url = md_match.group(1)
            # Download async
            async with httpx.AsyncClient(timeout=30.0) as client:
                img_response = await client.get(image_url)
                img_response.raise_for_status()
                return img_response.content
        else:
            # Check for base64
            data_match = re.search(r'(data:image/[^;]+;base64,[A-Za-z0-9+/=]+)', message)
            if data_match:
                data_url = data_match.group(1)
                # Extract base64 data
                header, encoded = data_url.split(',', 1)
                return base64.b64decode(encoded)
            else:
                raise Exception("Could not extract image from response")
