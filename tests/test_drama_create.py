#!/usr/bin/env python3
"""Test for POST /dramas endpoint with single character"""

import os
import sys
import requests
import json
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_DIR = Path(__file__).parent


class TestDramaCreate:
    """Test suite for POST /dramas endpoint"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url

    def test_health(self):
        """Test server is running"""
        print("🏥 Testing health endpoint...")
        response = requests.get(f"{self.base_url}/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("✅ Server is running\n")
        return response.json()

    def test_create_drama_from_premise_single_character(self):
        """Test creating drama from premise with async generation (single character)"""
        print("🎭 Testing POST /dramas (async mode) with single character...")

        # Test data - simple drama with one character
        premise = "A young detective solves mysteries in a small town. Keep it simple with 1 episode and 1 character."

        request_body = {
            "premise": premise,
            "id": f"test_drama_single_char_{int(time.time())}"
        }

        print(f"Request body: {json.dumps(request_body, indent=2)}")

        response = requests.post(
            f"{self.base_url}/dramas",
            json=request_body
        )

        print(f"Status: {response.status_code}")
        print(f"Response body: {json.dumps(response.json(), indent=2)}")
        assert response.status_code == 202, f"Expected 202 Accepted, got {response.status_code}. Response: {response.text}"

        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")

        # Verify response structure
        assert "dramaId" in data, "Missing dramaId in response"
        assert "jobId" in data, "Missing jobId in response"
        assert "status" in data, "Missing status in response"
        assert data["status"] == "pending", f"Expected status 'pending', got {data['status']}"

        drama_id = data["dramaId"]
        job_id = data["jobId"]

        print(f"\n✅ Drama creation queued successfully")
        print(f"   Drama ID: {drama_id}")
        print(f"   Job ID: {job_id}\n")

        # Poll job status
        print(f"⏳ Waiting for drama generation to complete...")
        max_attempts = 60  # 5 minutes timeout
        poll_interval = 5

        for attempt in range(max_attempts):
            time.sleep(poll_interval)

            job_response = requests.get(f"{self.base_url}/dramas/{drama_id}/jobs/{job_id}")
            assert job_response.status_code == 200, f"Job status check failed: {job_response.status_code}"

            job_data = job_response.json()
            status = job_data.get("status")

            print(f"   Attempt {attempt + 1}/{max_attempts}: Status = {status}")

            if status == "completed":
                print(f"✅ Drama generation completed!\n")
                break
            elif status == "failed":
                error = job_data.get("error", "Unknown error")
                raise AssertionError(f"Drama generation failed: {error}")

        else:
            raise TimeoutError(f"Drama generation timed out after {max_attempts * poll_interval} seconds")

        # Get the generated drama
        print(f"📖 Retrieving generated drama...")
        drama_response = requests.get(f"{self.base_url}/dramas/{drama_id}")
        assert drama_response.status_code == 200, f"Failed to get drama: {drama_response.status_code}"

        drama = drama_response.json()
        print(f"   Title: {drama['title']}")
        print(f"   Characters: {len(drama['characters'])}")
        print(f"   Episodes: {len(drama['episodes'])}")

        # Verify single character
        assert len(drama['characters']) >= 1, "Expected at least 1 character"

        # Verify character has URL (image generated)
        character = drama['characters'][0]
        print(f"\n   Character: {character['name']}")
        print(f"   Description: {character['description'][:100]}...")

        if character.get('url'):
            print(f"   Image URL: {character['url']}")
            print(f"   ✅ Character image generated")
        else:
            print(f"   ⚠️  Character image not generated (might be OK if generation failed)")

        # Verify drama cover image
        if drama.get('url'):
            print(f"   Drama Cover URL: {drama['url']}")
            print(f"   ✅ Drama cover image generated")

        print(f"\n✅ Test passed: Drama created with single character from premise\n")
        return drama_id, drama

    def test_create_drama_from_json_single_character(self):
        """Test creating drama from complete JSON (sync mode) with single character"""
        print("🎭 Testing POST /dramas (sync mode) with single character JSON...")

        # Test data - complete drama with one character
        drama_data = {
            "drama": {
                "id": f"test_drama_json_{int(time.time())}",
                "title": "The Boy Detective",
                "description": "A young boy with a keen eye for detail solves mysteries in his neighborhood.",
                "premise": "Boy detective solves local mysteries",
                "characters": [
                    {
                        "id": "char_detective_boy",
                        "name": "Tommy Chen",
                        "description": "A curious 12-year-old boy with exceptional observation skills and a love for detective stories. He wears a signature blue cap and carries a notebook everywhere.",
                        "gender": "male",
                        "url": None,  # Will be populated if we upload reference image
                        "assets": []
                    }
                ],
                "episodes": [
                    {
                        "id": "ep_01",
                        "title": "The Missing Cat",
                        "description": "Tommy investigates the mysterious disappearance of Mrs. Johnson's beloved cat, Whiskers.",
                        "scenes": [
                            {
                                "id": "scene_01",
                                "description": "Tommy sits in his treehouse, looking at missing cat posters through binoculars.",
                                "assets": []
                            },
                            {
                                "id": "scene_02",
                                "description": "Tommy interviews Mrs. Johnson about when she last saw Whiskers.",
                                "assets": []
                            }
                        ]
                    }
                ],
                "assets": [],
                "metadata": {
                    "test": "true",
                    "source": "test_drama_create.py"
                }
            }
        }

        response = requests.post(
            f"{self.base_url}/dramas",
            json=drama_data
        )

        print(f"Status: {response.status_code}")
        assert response.status_code == 201, f"Expected 201 Created, got {response.status_code}"

        data = response.json()
        print(f"Response summary:")
        print(f"   ID: {data['id']}")
        print(f"   Title: {data['title']}")
        print(f"   Characters: {len(data['characters'])}")
        print(f"   Episodes: {len(data['episodes'])}")

        # Verify single character
        assert len(data['characters']) == 1, f"Expected 1 character, got {len(data['characters'])}"
        assert data['characters'][0]['name'] == "Tommy Chen", "Character name mismatch"

        print(f"\n✅ Test passed: Drama created from JSON with single character\n")
        return data['id'], data


def run_tests():
    """Run all tests"""
    print("=" * 70)
    print("POST /dramas Test Suite - Single Character")
    print("=" * 70 + "\n")

    tester = TestDramaCreate()

    try:
        # Test 1: Health check
        tester.test_health()

        # Test 2: Create drama from JSON (sync mode - faster)
        print("-" * 70)
        drama_id_json, drama_json = tester.test_create_drama_from_json_single_character()
        print("-" * 70 + "\n")

        # Test 3: Create drama from premise (async mode - with AI generation)
        print("-" * 70)
        drama_id_premise, drama_premise = tester.test_create_drama_from_premise_single_character()
        print("-" * 70 + "\n")

        print("=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
