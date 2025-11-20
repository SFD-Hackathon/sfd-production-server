"""
Tests for video stitching functionality.

Tests the stitch_local_videos() core function using test video assets.
"""

import os
import shutil
from pathlib import Path

import pytest
from moviepy.editor import VideoFileClip

from app.video_stitching import stitch_local_videos

# Test directory
TEST_DIR = Path(__file__).parent
ASSETS_DIR = TEST_DIR / "assets"


def test_stitch_two_videos():
    """
    Test stitching two test videos into a single video.

    This test:
    1. Uses test_video_1.mp4 and test_video_2.mp4 from tests/assets/
    2. Calls stitch_local_videos() to combine them
    3. Verifies output file exists and has expected properties
    4. Cleans up output files
    """
    # Verify test videos exist
    video1_path = ASSETS_DIR / "test_video_1.mp4"
    video2_path = ASSETS_DIR / "test_video_2.mp4"

    assert video1_path.exists(), f"Test video 1 not found: {video1_path}"
    assert video2_path.exists(), f"Test video 2 not found: {video2_path}"

    print(f"\n✓ Found test videos:")
    print(f"  - {video1_path.name} ({video1_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  - {video2_path.name} ({video2_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Create output directory
    output_dir = Path("./outputs/test_stitch")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "stitched_episode.mp4"

    try:
        print(f"\n⚙️  Stitching videos...")

        # Call core stitching function with local paths
        result_path = stitch_local_videos(
            video_paths=[str(video1_path), str(video2_path)],
            output_path=str(output_path)
        )

        # Verify output
        assert Path(result_path).exists(), f"Stitched video not found: {result_path}"
        assert result_path == str(output_path), "Result path should match output_path"

        print(f"\n✓ Stitching successful!")
        print(f"  Output: {result_path}")

        # Verify file size is reasonable (non-zero, not corrupted)
        stitched_size = Path(result_path).stat().st_size
        assert stitched_size > 0, "Stitched video should have non-zero size"
        print(f"  Stitched size: {stitched_size / 1024 / 1024:.1f} MB")

        # Proper validation: check video duration (should equal sum of inputs)
        # Load video clips to get durations
        video1_clip = VideoFileClip(str(video1_path))
        video2_clip = VideoFileClip(str(video2_path))
        stitched_clip = VideoFileClip(result_path)

        try:
            video1_duration = video1_clip.duration
            video2_duration = video2_clip.duration
            stitched_duration = stitched_clip.duration

            expected_duration = video1_duration + video2_duration

            # Allow small tolerance (0.5s) for frame alignment
            tolerance = 0.5
            duration_diff = abs(stitched_duration - expected_duration)

            print(f"\n  ✓ Duration validation:")
            print(f"    Video 1: {video1_duration:.2f}s")
            print(f"    Video 2: {video2_duration:.2f}s")
            print(f"    Expected: {expected_duration:.2f}s")
            print(f"    Stitched: {stitched_duration:.2f}s")
            print(f"    Difference: {duration_diff:.2f}s")

            assert duration_diff <= tolerance, (
                f"Stitched duration ({stitched_duration:.2f}s) differs from expected "
                f"({expected_duration:.2f}s) by {duration_diff:.2f}s (tolerance: {tolerance}s)"
            )

            print(f"  ✓ Duration validation passed!")

        finally:
            # Clean up moviepy resources
            video1_clip.close()
            video2_clip.close()
            stitched_clip.close()

    finally:
        # Cleanup
        if output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)
            print(f"\n✓ Cleaned up temp directory")


if __name__ == "__main__":
    # Run test directly
    print("=" * 60)
    print("Testing video stitching functionality")
    print("=" * 60)

    test_stitch_two_videos()

    print("\n" + "=" * 60)
    print("✓ Test passed!")
    print("=" * 60)

