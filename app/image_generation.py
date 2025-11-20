"""
Image generation using Gemini API.

Separate module to avoid circular imports between asset_api and generation_dag_engine.
Provides both sync and async interfaces with retry logic and R2 upload support.
"""

import os
import base64
import re
import requests
import httpx
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.config import MAX_RETRIES, NANO_BANANA_API_KEY, NANO_BANANA_API_BASE


def generate_image(prompt: str, output_path: str, reference_images: list = None, max_retries: int = None):
    """
    Generate an image using Gemini API and save to local file.
    Includes retry logic for robustness.

    Args:
        prompt: Text description of the image to generate
        output_path: Local path to save the generated image
        reference_images: Optional list of reference image paths (local or URL)
        max_retries: Number of retry attempts (default: from config MAX_RETRIES)

    Returns:
        Dict with 'path' and 'url' (path to saved file)

    Raises:
        Exception: If generation fails after all retries
    """
    if max_retries is None:
        max_retries = MAX_RETRIES

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return _generate_image_single_attempt(prompt, output_path, reference_images)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"⚠️  Image generation attempt {attempt + 1} failed: {e}. Retrying...")
                continue
            else:
                print(f"❌ Image generation failed after {max_retries + 1} attempts")
                raise last_error


def _generate_image_single_attempt(prompt: str, output_path: str, reference_images: list = None):
    # Build prompt
    full_prompt = f"CRITICAL REQUIREMENT: STRICT VERTICAL PORTRAIT FORMAT - 9:16 aspect ratio (1080x1920 pixels). The image MUST be taller than it is wide. Vertical orientation is MANDATORY.\n\nIMAGE CONTENT: {prompt}\n\nSTYLE: Anime style, cartoon illustration, vibrant colors, clean lines."

    # Build request - convert reference images to base64 if provided
    if reference_images:
        content = [{"type": "text", "text": full_prompt}]
        for ref in reference_images:
            try:
                # Check if it's already a data URL (base64)
                if ref.startswith('data:image/'):
                    content.append({"type": "image_url", "image_url": {"url": ref}})
                    continue

                # Check if it's a local file
                if os.path.exists(ref):
                    with open(ref, 'rb') as f:
                        ref_bytes = f.read()
                    ref_base64 = base64.b64encode(ref_bytes).decode('utf-8')
                    # Determine image type from extension
                    ext = ref.rsplit('.', 1)[-1].lower() if '.' in ref else 'png'
                    content_type = f'image/{ext}' if ext in ['png', 'jpeg', 'jpg', 'webp'] else 'image/png'
                    data_url = f"data:{content_type};base64,{ref_base64}"
                    content.append({"type": "image_url", "image_url": {"url": data_url}})
                    continue

                # Try to download from URL
                ref_response = requests.get(ref, timeout=10)
                ref_response.raise_for_status()
                ref_base64 = base64.b64encode(ref_response.content).decode('utf-8')
                content_type = ref_response.headers.get('content-type', 'image/png')
                data_url = f"data:{content_type};base64,{ref_base64}"
                content.append({"type": "image_url", "image_url": {"url": data_url}})
            except Exception as e:
                print(f"WARNING: Failed to process reference image {ref}: {e}")
                continue
    else:
        content = full_prompt

    payload = {
        "model": "gemini-2.5-flash-image",
        "messages": [{"role": "user", "content": content}],
        "stream": False
    }

    headers = {
        "Authorization": f"Bearer {NANO_BANANA_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{NANO_BANANA_API_BASE}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as e:
        raise Exception(f"Failed to parse Gemini API response as JSON. Status: {response.status_code}, Content: {response.text[:200]}")

    # Extract image from response
    message = result['choices'][0]['message']['content']

    # Check for markdown image URL
    md_match = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', message)
    if md_match:
        image_url = md_match.group(1)
        # Download and save
        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()
        image_bytes = img_response.content
    else:
        # Check for base64
        data_match = re.search(r'(data:image/[^;]+;base64,[A-Za-z0-9+/=]+)', message)
        if data_match:
            data_url = data_match.group(1)
            # Extract base64 data
            header, encoded = data_url.split(',', 1)
            image_bytes = base64.b64decode(encoded)
        else:
            raise Exception("Could not extract image from response")

    # Save to local file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(image_bytes)

    print(f"✓ Generated image saved to {output_path}")

    return {
        'path': output_path,
        'url': f"file://{output_path}"  # Local file URL
    }


async def generate_image_async(
    prompt: str,
    reference_images: Optional[List[str]] = None,
    max_retries: Optional[int] = None
) -> bytes:
    """
    Generate an image using Gemini API asynchronously and return image bytes.
    Includes retry logic for robustness.

    Args:
        prompt: Text description of the image to generate
        reference_images: Optional list of reference image URLs
        max_retries: Number of retry attempts (default: from config MAX_RETRIES)

    Returns:
        Image bytes

    Raises:
        Exception: If generation fails after all retries
    """
    if max_retries is None:
        max_retries = MAX_RETRIES

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await _generate_image_async_single_attempt(prompt, reference_images)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"⚠️  Image generation attempt {attempt + 1} failed: {e}. Retrying...")
                await asyncio.sleep(2)  # Brief delay before retry
                continue
            else:
                print(f"❌ Image generation failed after {max_retries + 1} attempts")
                raise last_error


async def _generate_image_async_single_attempt(
    prompt: str,
    reference_images: Optional[List[str]] = None
) -> bytes:
    """Single async attempt to generate image"""
    # Build full prompt with vertical format requirement
    full_prompt = f"CRITICAL REQUIREMENT: STRICT VERTICAL PORTRAIT FORMAT - 9:16 aspect ratio (1080x1920 pixels). The image MUST be taller than it is wide. Vertical orientation is MANDATORY.\n\nIMAGE CONTENT: {prompt}\n\nSTYLE: Anime style, cartoon illustration, vibrant colors, clean lines."

    # Build request content
    content = [{"type": "text", "text": full_prompt}]

    # Add reference images if provided
    if reference_images:
        for ref in reference_images:
            content.append({"type": "image_url", "image_url": {"url": ref}})

    # Build API request payload
    payload = {
        "model": "gemini-2.5-flash-image",
        "messages": [{"role": "user", "content": content}],
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {NANO_BANANA_API_KEY}",
        "Content-Type": "application/json",
    }

    # Make async API request
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{NANO_BANANA_API_BASE}/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()

    try:
        result = response.json()
    except ValueError as e:
        raise Exception(f"Failed to parse Gemini API response as JSON. Status: {response.status_code}, Content: {response.text[:200]}")

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
