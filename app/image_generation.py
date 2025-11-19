"""
Image generation using Gemini API.

Separate module to avoid circular imports between asset_api and generation_dag_engine.
"""

import os
import base64
import re
import requests
from pathlib import Path

from config import GEMINI_API_KEY, GEMINI_API_BASE


def generate_image(prompt: str, output_path: str, reference_images: list = None):
    """
    Generate an image using Gemini API and save to local file.

    Args:
        prompt: Text description of the image to generate
        output_path: Local path to save the generated image
        reference_images: Optional list of reference image paths (local or URL)

    Returns:
        Dict with 'path' and 'url' (path to saved file)

    Raises:
        Exception: If generation fails
    """
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
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{GEMINI_API_BASE}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()
    result = response.json()

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
