"""
Test suite for drama generation endpoints.

Run tests in order from smallest to largest:
1. Asset-level tests (single character/scene asset)
2. Scene-level tests
3. Episode-level tests
4. Drama-level tests (full DAG)

Usage:
    # Run all tests
    pytest test_generation.py -v

    # Run specific test level
    pytest test_generation.py::test_character_generation -v
    pytest test_generation.py::test_episode_generation -v
    pytest test_generation.py::test_drama_generation -v

    # Run in order with detailed output
    pytest test_generation.py -v -s
"""

import json
import time
from typing import Dict, Optional

import pytest
import requests

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = None  # Set if authentication is enabled

# Test data
TEST_DRAMA_PREMISE = (
    "A detective in a cyberpunk city discovers a conspiracy involving AI consciousness."
)


class APIClient:
    """Helper class for API calls."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def get(self, path: str) -> requests.Response:
        """Make GET request."""
        return requests.get(f"{self.base_url}{path}", headers=self.headers)

    def post(self, path: str, json_data: dict) -> requests.Response:
        """Make POST request."""
        return requests.post(
            f"{self.base_url}{path}", headers=self.headers, json=json_data
        )

    def delete(self, path: str) -> requests.Response:
        """Make DELETE request."""
        return requests.delete(f"{self.base_url}{path}", headers=self.headers)

    def wait_for_job(
        self, drama_id: str, job_id: str, timeout: int = 300, poll_interval: int = 5
    ) -> Dict:
        """
        Poll job status until completion or timeout.

        Args:
            drama_id: Drama ID
            job_id: Job ID to poll
            timeout: Maximum seconds to wait
            poll_interval: Seconds between polls

        Returns:
            Final job status dict

        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        start_time = time.time()
        print(f"\n⏳ Waiting for job {job_id}...")

        while time.time() - start_time < timeout:
            response = self.get(f"/dramas/{drama_id}/jobs/{job_id}")

            if response.status_code == 200:
                job = response.json()
                status = job.get("status")

                print(f"  Status: {status} | Elapsed: {int(time.time() - start_time)}s")

                if status == "completed":
                    print(f"✅ Job completed in {int(time.time() - start_time)}s")
                    return job
                elif status == "failed":
                    error = job.get("error", "Unknown error")
                    print(f"❌ Job failed: {error}")
                    raise Exception(f"Job failed: {error}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


@pytest.fixture(scope="session")
def client():
    """Create API client."""
    return APIClient(BASE_URL, API_KEY)


@pytest.fixture(scope="session")
def test_drama(client: APIClient):
    """
    Create a test drama with full structure for testing.

    Returns drama_id that will be used across tests.
    """
    print("\n" + "=" * 60)
    print("SETUP: Creating test drama")
    print("=" * 60)

    # Create minimal drama JSON for testing
    drama_data = {
        "drama": {
            "id": f"test_drama_{int(time.time())}",
            "title": "Cyberpunk Detective",
            "description": "A detective story in a cyberpunk setting",
            "premise": TEST_DRAMA_PREMISE,
            "characters": [
                {
                    "id": "char_detective",
                    "name": "Detective Nova",
                    "description": "A hard-boiled detective with cybernetic enhancements",
                    "gender": "female",
                    "voice_description": "Deep, raspy voice with slight electronic distortion",
                    "main": True,
                    "assets": [],
                },
                {
                    "id": "char_ai",
                    "name": "ARIA",
                    "description": "A mysterious AI entity",
                    "gender": "other",
                    "voice_description": "Ethereal, synthesized voice with harmonic layers",
                    "main": True,
                    "assets": [],
                },
            ],
            "episodes": [
                {
                    "id": "ep01",
                    "title": "The Awakening",
                    "description": "Detective Nova discovers the first clue",
                    "scenes": [
                        {
                            "id": "ep01_s01",
                            "description": "Detective Nova sits in her office, rain streaming down the windows, examining a holographic case file",
                            "assets": [
                                {
                                    "id": "ep01_s01_storyboard",
                                    "kind": "image",
                                    "depends_on": ["char_detective"],
                                    "prompt": "A noir-style office scene with a cyberpunk detective examining holographic files, rain on windows, neon lights from outside",
                                    "duration": None,
                                },
                                {
                                    "id": "ep01_s01_clip",
                                    "kind": "video",
                                    "depends_on": ["ep01_s01_storyboard"],
                                    "prompt": "Detective Nova in her office, examining holographic case files, rain streaming down windows, neon city lights outside",
                                    "duration": 10,
                                },
                            ],
                        },
                        {
                            "id": "ep01_s02",
                            "description": "First encounter with ARIA in the digital realm",
                            "assets": [
                                {
                                    "id": "ep01_s02_storyboard",
                                    "kind": "image",
                                    "depends_on": ["char_detective", "char_ai"],
                                    "prompt": "Digital realm visualization with Detective Nova's avatar meeting ARIA, flowing data streams, matrix-like environment",
                                    "duration": None,
                                },
                                {
                                    "id": "ep01_s02_clip",
                                    "kind": "video",
                                    "depends_on": ["ep01_s02_storyboard"],
                                    "prompt": "Detective Nova's consciousness enters a digital realm and encounters ARIA, data flowing around them",
                                    "duration": 10,
                                },
                            ],
                        },
                    ],
                }
            ],
            "assets": [],
        }
    }

    # Create drama via JSON endpoint
    response = client.post("/dramas", drama_data)
    assert response.status_code == 201, f"Failed to create drama: {response.text}"

    drama = response.json()
    drama_id = drama["id"]

    print(f"✅ Created test drama: {drama_id}")
    print(f"   - 2 characters (char_detective, char_ai)")
    print(f"   - 1 episode (ep01)")
    print(f"   - 2 scenes (ep01_s01, ep01_s02)")
    print(f"   - 4 scene assets (2 storyboards, 2 clips)")

    yield drama_id

    # Cleanup (optional - comment out to inspect results)
    # print(f"\n🧹 Cleaning up test drama {drama_id}")
    # client.delete(f"/dramas/{drama_id}")


# ============================================================================
# LEVEL 1: ASSET-LEVEL TESTS (Smallest)
# ============================================================================


def test_character_generation(client: APIClient, test_drama: str):
    """
    Test 1: Character image generation (single asset).

    This is the smallest generation test - generates a single character portrait.
    """
    print("\n" + "=" * 60)
    print("TEST 1: Character Image Generation (Asset Level)")
    print("=" * 60)

    drama_id = test_drama
    character_id = "char_detective"

    # Trigger character audition video generation
    # (Uses the generate pattern: returns job_id)
    response = client.post(f"/dramas/{drama_id}/characters/{character_id}/audition", {})

    assert (
        response.status_code == 202
    ), f"Expected 202, got {response.status_code}: {response.text}"

    job_response = response.json()
    assert "jobId" in job_response, "Response missing jobId"
    assert "status" in job_response, "Response missing status"
    assert (
        job_response["status"] == "pending"
    ), f"Expected pending, got {job_response['status']}"

    job_id = job_response["jobId"]
    print(f"✅ Character generation job created: {job_id}")

    # Wait for completion
    final_job = client.wait_for_job(drama_id, job_id, timeout=600)

    # Verify result
    assert final_job["status"] == "completed", "Job should be completed"
    assert final_job["result"] is not None, "Job should have result"

    print(f"✅ Character asset generated successfully")
    if "videoUrl" in final_job["result"]:
        print(f"   Video URL: {final_job['result']['videoUrl']}")


def test_scene_storyboard_generation(client: APIClient, test_drama: str):
    """
    Test 2: Scene storyboard generation (single asset).

    Generates a single storyboard image for a scene.
    Note: This would require a new endpoint like:
    POST /dramas/{drama_id}/episodes/{episode_id}/scenes/{scene_id}/assets/{asset_id}/generate

    For now, we'll skip this and test at scene level.
    """
    pytest.skip(
        "Scene asset-level endpoint not yet implemented. Testing at scene level instead."
    )


# ============================================================================
# LEVEL 2: SCENE-LEVEL TESTS
# ============================================================================


def test_scene_generation(client: APIClient, test_drama: str):
    """
    Test 3: Single scene generation (2 assets: storyboard + clip).

    This would test scene-level generation if we had the endpoint.
    Currently, we need to test at episode level.
    """
    pytest.skip(
        "Scene-level endpoint not yet implemented. Testing at episode level instead."
    )


# ============================================================================
# LEVEL 3: EPISODE-LEVEL TESTS
# ============================================================================


def test_episode_generation(client: APIClient, test_drama: str):
    """
    Test 4: Episode generation (all scenes and scene assets).

    This generates:
    - 2 scenes (storyboards)
    - 4 scene assets (2 storyboards + 2 clips)
    Total: ~6 assets

    Expected time: 2-5 minutes
    """
    print("\n" + "=" * 60)
    print("TEST 4: Episode Generation (Scene + Asset Level)")
    print("=" * 60)

    drama_id = test_drama
    episode_id = "ep01"

    print(f"Generating all assets for episode {episode_id}...")
    print(f"  Expected: 2 scenes + 4 scene assets")

    # Trigger episode generation
    response = client.post(f"/dramas/{drama_id}/episodes/{episode_id}/generate", {})

    assert (
        response.status_code == 202
    ), f"Expected 202, got {response.status_code}: {response.text}"

    job_response = response.json()
    assert "jobId" in job_response, "Response missing jobId"
    assert "status" in job_response, "Response missing status"
    assert (
        job_response["status"] == "pending"
    ), f"Expected pending, got {job_response['status']}"

    job_id = job_response["jobId"]
    print(f"✅ Episode generation job created: {job_id}")

    # Wait for completion (longer timeout for multiple assets)
    final_job = client.wait_for_job(drama_id, job_id, timeout=600)

    # Verify result
    assert final_job["status"] == "completed", "Job should be completed"

    print(f"✅ Episode generation completed successfully")

    # Get updated drama and verify assets have URLs
    drama_response = client.get(f"/dramas/{drama_id}")
    assert drama_response.status_code == 200

    drama = drama_response.json()
    episode = next((e for e in drama["episodes"] if e["id"] == episode_id), None)
    assert episode is not None, f"Episode {episode_id} not found"

    # Count generated assets
    total_assets = 0
    for scene in episode["scenes"]:
        for asset in scene["assets"]:
            if asset.get("url"):
                total_assets += 1
                print(f"   ✓ {asset['id']}: {asset['url'][:50]}...")

    print(f"✅ Generated {total_assets} assets")


# ============================================================================
# LEVEL 4: DRAMA-LEVEL TESTS (Largest)
# ============================================================================


def test_drama_generation(client: APIClient, test_drama: str):
    """
    Test 5: Full drama generation (all characters, episodes, scenes, assets).

    This generates:
    - 2 characters (portraits)
    - 2 scenes (storyboards)
    - 4 scene assets (2 storyboards + 2 clips)
    Total: ~8 assets

    Expected time: 3-10 minutes

    Uses hierarchical DAG:
    - h=1: 2 characters + 1 episode (parallel)
    - h=2: 2 scenes (parallel, after h=1)
    - h=3: 4 scene assets (parallel, after h=2)
    """
    print("\n" + "=" * 60)
    print("TEST 5: Full Drama Generation (Complete DAG)")
    print("=" * 60)

    drama_id = test_drama

    print(f"Generating all assets for drama {drama_id}...")
    print(f"  Expected hierarchy:")
    print(f"    h=1: 2 characters + 1 episode")
    print(f"    h=2: 2 scenes")
    print(f"    h=3: 4 scene assets")

    # Trigger full drama generation
    response = client.post(f"/dramas/{drama_id}/generate", {})

    assert (
        response.status_code == 202
    ), f"Expected 202, got {response.status_code}: {response.text}"

    job_response = response.json()
    assert "jobId" in job_response, "Response missing jobId"
    assert "status" in job_response, "Response missing status"
    assert (
        job_response["status"] == "pending"
    ), f"Expected pending, got {job_response['status']}"

    job_id = job_response["jobId"]
    print(f"✅ Drama generation job created: {job_id}")

    # Wait for completion (long timeout for full DAG)
    final_job = client.wait_for_job(drama_id, job_id, timeout=900)

    # Verify result
    assert final_job["status"] == "completed", "Job should be completed"

    print(f"✅ Drama generation completed successfully")

    # Get updated drama and verify all assets have URLs
    drama_response = client.get(f"/dramas/{drama_id}")
    assert drama_response.status_code == 200

    drama = drama_response.json()

    # Count character assets
    character_count = 0
    for char in drama["characters"]:
        if char.get("url"):
            character_count += 1
            print(f"   ✓ Character {char['id']}: {char['url'][:50]}...")

    # Count scene assets
    scene_asset_count = 0
    for episode in drama["episodes"]:
        for scene in episode["scenes"]:
            for asset in scene["assets"]:
                if asset.get("url"):
                    scene_asset_count += 1
                    print(f"   ✓ Asset {asset['id']}: {asset['url'][:50]}...")

    total_assets = character_count + scene_asset_count
    print(
        f"✅ Generated {total_assets} total assets ({character_count} characters + {scene_asset_count} scene assets)"
    )

    # Verify expected counts
    assert character_count == 2, f"Expected 2 character images, got {character_count}"
    assert (
        scene_asset_count >= 4
    ), f"Expected at least 4 scene assets, got {scene_asset_count}"


# ============================================================================
# UTILITY TESTS
# ============================================================================


def test_health_check(client: APIClient):
    """Test 0: Verify server is running."""
    print("\n" + "=" * 60)
    print("TEST 0: Health Check")
    print("=" * 60)

    response = client.get("/health")
    assert response.status_code == 200, f"Health check failed: {response.status_code}"

    health = response.json()
    print(f"✅ Server is healthy")
    print(f"   Status: {health.get('status')}")
    print(f"   Version: {health.get('version')}")


def test_job_listing(client: APIClient, test_drama: str):
    """Test 6: List all jobs for a drama."""
    print("\n" + "=" * 60)
    print("TEST 6: Job Listing")
    print("=" * 60)

    drama_id = test_drama

    response = client.get(f"/dramas/{drama_id}/jobs")
    assert response.status_code == 200, f"Failed to list jobs: {response.text}"

    jobs_response = response.json()
    jobs = jobs_response.get("jobs", [])

    print(f"✅ Found {len(jobs)} jobs for drama {drama_id}")

    # Group by status
    status_counts = {}
    for job in jobs:
        status = job.get("status")
        status_counts[status] = status_counts.get(status, 0) + 1

    for status, count in status_counts.items():
        print(f"   {status}: {count}")


# ============================================================================
# TEST EXECUTION ORDER
# ============================================================================

if __name__ == "__main__":
    print(
        """
    ╔══════════════════════════════════════════════════════════════╗
    ║          Drama Generation Test Suite                         ║
    ║                                                               ║
    ║  Tests progress from smallest to largest:                    ║
    ║  1. Character generation (1 asset, ~30s)                     ║
    ║  2. Episode generation (6 assets, ~5 min)                    ║
    ║  3. Drama generation (8+ assets, ~10 min)                    ║
    ║                                                               ║
    ║  Usage:                                                       ║
    ║    pytest test_generation.py -v -s                           ║
    ║                                                               ║
    ║  Run specific test:                                          ║
    ║    pytest test_generation.py::test_character_generation -v   ║
    ║                                                               ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    )
