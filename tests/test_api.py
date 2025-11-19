#!/usr/bin/env python3
"""Simple test script for Drama API"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    print("🏥 Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200


def test_create_drama():
    """Test drama creation from premise"""
    print("🎭 Creating drama from premise...")
    premise = "A time traveler discovers they can only go backwards. Make it emotional with 2 episodes."

    response = requests.post(
        f"{BASE_URL}/dramas",
        json={"premise": premise},
    )

    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}\n")

    if response.status_code == 202:
        drama_id = data["dramaId"]
        job_id = data["jobId"]
        return drama_id, job_id
    return None, None


def test_job_status(drama_id, job_id):
    """Test job status checking"""
    print(f"⏳ Checking job status for {job_id}...")

    max_attempts = 30
    for i in range(max_attempts):
        response = requests.get(f"{BASE_URL}/dramas/{drama_id}/jobs/{job_id}")

        if response.status_code == 200:
            data = response.json()
            status = data["status"]
            print(f"Attempt {i+1}: Status = {status}")

            if status == "completed":
                print(f"✅ Job completed!\n")
                return True
            elif status == "failed":
                print(f"❌ Job failed: {data.get('error', 'Unknown error')}\n")
                return False

        time.sleep(5)

    print(f"⏰ Timeout waiting for job completion\n")
    return False


def test_get_drama(drama_id):
    """Test getting drama by ID"""
    print(f"📖 Getting drama {drama_id}...")

    response = requests.get(f"{BASE_URL}/dramas/{drama_id}")

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Title: {data['title']}")
        print(f"Description: {data['description']}")
        print(f"Episodes: {len(data['episodes'])}")
        print(f"Characters: {len(data['characters'])}\n")
        return True
    return False


def test_list_dramas():
    """Test listing dramas"""
    print("📚 Listing dramas...")

    response = requests.get(f"{BASE_URL}/dramas")

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Found {len(data['dramas'])} dramas\n")
        return True
    return False


def main():
    """Run all tests"""
    print("=" * 50)
    print("Drama API Test Suite")
    print("=" * 50 + "\n")

    # Test health
    if not test_health():
        print("❌ Health check failed. Is the server running?")
        return

    # Test drama creation
    drama_id, job_id = test_create_drama()
    if not drama_id:
        print("❌ Drama creation failed")
        return

    # Test job status
    if not test_job_status(drama_id, job_id):
        print("❌ Job did not complete successfully")
        # Continue anyway to test other endpoints

    # Test get drama
    test_get_drama(drama_id)

    # Test list dramas
    test_list_dramas()

    print("=" * 50)
    print("✅ Tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
