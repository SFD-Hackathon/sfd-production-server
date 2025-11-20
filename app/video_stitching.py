"""
Video stitching for episode generation.

Combines multiple scene videos into a single episode video using moviepy.
"""

import os
import logging
import shutil
from typing import Tuple, List
from pathlib import Path

import requests
from moviepy.editor import VideoFileClip, concatenate_videoclips

from app.models import Episode, AssetKind
from app.config import OUTPUTS_DIR

logger = logging.getLogger(__name__)


def stitch_local_videos(
    video_paths: List[str],
    output_path: str
) -> str:
    """
    Stitch multiple local MP4 videos into a single video.

    This is the core video stitching logic separated for easy unit testing.

    Args:
        video_paths: List of local paths to MP4 files to stitch (in order)
        output_path: Path where the stitched video should be saved

    Returns:
        Path to the stitched video file (same as output_path)

    Raises:
        ValueError: If video_paths is empty or files don't exist
        RuntimeError: If video stitching fails

    Example:
        >>> stitched = stitch_local_videos(
        ...     video_paths=["scene1.mp4", "scene2.mp4"],
        ...     output_path="episode.mp4"
        ... )
        >>> print(stitched)
        episode.mp4
    """
    if not video_paths:
        raise ValueError("video_paths cannot be empty")

    # Verify all input files exist
    for path in video_paths:
        if not Path(path).exists():
            raise ValueError(f"Video file not found: {path}")

    logger.info(f"Stitching {len(video_paths)} videos into {output_path}")

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        # Load video clips
        clips = [VideoFileClip(path) for path in video_paths]

        # Concatenate with compose method (handles different dimensions)
        final_clip = concatenate_videoclips(clips, method="compose")

        # Write output with H.264 codec (matches Sora output)
        final_clip.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="medium",
            logger=None  # Suppress moviepy progress bar in logs
        )

        # Clean up moviepy resources
        for clip in clips:
            clip.close()
        final_clip.close()

        logger.info(f"✓ Stitched video: {output_path}")

        return str(output_path)

    except Exception as e:
        logger.error(f"Failed to stitch videos: {e}")
        raise RuntimeError(f"Video stitching failed: {e}")


def stitch_episode_videos(
    episode: Episode,
    drama_id: str,
    upload_to_r2: bool = True
) -> Tuple[str, str, str]:
    """
    Stitch all scene videos for one episode into a single video.

    Workflow:
    1. Collect video URLs from episode.scenes[].assets[] (one video per scene)
    2. Download videos from R2 to local temp directory
    3. Use moviepy.concatenate_videoclips() to stitch in scene order
    4. Upload stitched MP4 to R2
    5. Clean up temp files

    Args:
        episode: Episode object containing scenes with video assets
        drama_id: Drama identifier for file organization
        upload_to_r2: Whether to upload to R2 (default: True, set False for testing)

    Returns:
        Tuple of (local_path, r2_url, r2_key):
            - local_path: Path to stitched MP4 file in outputs/
            - r2_url: Public CDN URL of uploaded video (None if upload_to_r2=False)
            - r2_key: R2 object key for reference (None if upload_to_r2=False)

    Raises:
        ValueError: If no video assets found or download fails
        RuntimeError: If video stitching or upload fails

    Example:
        >>> local_path, r2_url, r2_key = stitch_episode_videos(
        ...     episode=drama.episodes[0],
        ...     drama_id="drama_abc123"
        ... )
        >>> print(r2_url)
        https://pub-xxx.r2.dev/dramas/drama_abc123/episodes/ep001.mp4
    """
    # 1. Collect video assets from scenes
    video_clips = []
    for scene in episode.scenes:
        for asset in scene.assets:
            # Only include video assets with URLs
            if asset.kind == AssetKind.video and asset.url:
                video_clips.append({
                    "scene_id": scene.id,
                    "asset_id": asset.id,
                    "url": asset.url,
                    "duration": asset.duration or 10
                })
                break  # Only one video per scene

    if not video_clips:
        raise ValueError(
            f"No video clips found for episode {episode.id}. "
            f"Ensure scenes have video assets with URLs."
        )

    logger.info(
        f"Found {len(video_clips)} video clips for episode {episode.id}"
    )

    # 2. Download videos to temp directory
    temp_dir = Path(OUTPUTS_DIR) / drama_id / "temp_stitch" / episode.id
    temp_dir.mkdir(parents=True, exist_ok=True)

    local_paths = []

    try:
        for idx, clip in enumerate(video_clips):
            local_path = temp_dir / f"scene_{idx:03d}_{clip['asset_id']}.mp4"

            # Download from R2 URL or copy from local file:// URL
            try:
                logger.info(f"Downloading scene video {idx+1}/{len(video_clips)}: {clip['url']}")

                # Handle file:// URLs for testing
                if clip['url'].startswith('file://'):
                    source_path = clip['url'].replace('file://', '')
                    import shutil as sh
                    sh.copy2(source_path, local_path)
                    logger.info(f"✓ Copied from local file: {local_path.name}")
                else:
                    # Download from HTTP/HTTPS URL
                    response = requests.get(clip["url"], stream=True, timeout=60)
                    response.raise_for_status()

                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    logger.info(f"✓ Downloaded: {local_path.name}")

                local_paths.append(str(local_path))

            except Exception as e:
                logger.error(f"Failed to download video {clip['url']}: {e}")
                raise ValueError(f"Failed to download scene video: {e}")

        # 3. Stitch videos using core function
        output_path = Path(OUTPUTS_DIR) / drama_id / f"episode_{episode.id}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Use core stitching function
            stitch_local_videos(local_paths, str(output_path))
        except Exception as e:
            logger.error(f"Failed to stitch episode videos: {e}")
            raise

        # 4. Upload stitched video to R2 (optional)
        if not upload_to_r2:
            logger.info("Skipping R2 upload (upload_to_r2=False)")
            return str(output_path), None, None

        try:
            from app.storage import storage

            r2_key = f"dramas/{drama_id}/episodes/{episode.id}.mp4"

            with open(output_path, 'rb') as f:
                storage.s3_client.put_object(
                    Bucket=storage.bucket_name,
                    Key=r2_key,
                    Body=f.read(),
                    ContentType="video/mp4"
                )

            r2_url = f"{storage.public_url_base}/{r2_key}"

            logger.info(f"✓ Uploaded episode video to R2: {r2_url}")

            return str(output_path), r2_url, r2_key

        except Exception as e:
            logger.error(f"Failed to upload stitched video: {e}")
            raise RuntimeError(f"R2 upload failed: {e}")

    finally:
        # Clean up temp files
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"✓ Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory: {e}")
