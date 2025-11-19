#!/usr/bin/env python3
"""
Test script for Gemini 3 Pro Preview model via t8star.cn API
Tests the /v1/chat/completions endpoint with drama generation prompt
"""

import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_BASE = os.getenv("GEMINI_API_BASE", "https://ai.t8star.cn")
MODEL = "gemini-3-pro-preview"

# Test prompt for drama generation
TEST_PROMPT = """Generate a short drama outline with the following:
- Title: A compelling drama title
- Description: Brief 2-3 sentence description
- 2 characters with names, descriptions, and gender
- 2 episodes with titles and descriptions

Keep the response concise and structured."""


async def test_gemini3_chat_completions():
    """Test Gemini 3 Pro Preview model via chat completions endpoint"""

    print("=" * 80)
    print("GEMINI 3 PRO PREVIEW TEST")
    print("=" * 80)
    print(f"API Base URL: {GEMINI_API_BASE}")
    print(f"Model: {MODEL}")
    print(f"API Key: {GEMINI_API_KEY[:20]}..." if GEMINI_API_KEY else "API Key: NOT SET")
    print("=" * 80)

    if not GEMINI_API_KEY:
        print("❌ ERROR: GEMINI_API_KEY not found in .env")
        return

    # Build API request
    url = f"{GEMINI_API_BASE}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert drama writer. Generate compelling short-form drama outlines."
            },
            {
                "role": "user",
                "content": TEST_PROMPT
            }
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    print("\n📤 REQUEST:")
    print(f"URL: {url}")
    print(f"Headers: {json.dumps({k: v[:50] + '...' if len(v) > 50 else v for k, v in headers.items()}, indent=2)}")
    print(f"Payload:")
    print(json.dumps(payload, indent=2))
    print("\n⏳ Sending request...")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            print(f"\n📥 RESPONSE:")
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")

            # Check if request was successful
            response.raise_for_status()

            # Parse response
            result = response.json()
            print(f"\n✅ SUCCESS!")
            print(f"Response JSON:")
            print(json.dumps(result, indent=2))

            # Extract and display generated content
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                print(f"\n📝 GENERATED CONTENT:")
                print("-" * 80)
                print(content)
                print("-" * 80)

                # Display usage stats if available
                if "usage" in result:
                    usage = result["usage"]
                    print(f"\n📊 USAGE STATS:")
                    print(f"  Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
                    print(f"  Completion tokens: {usage.get('completion_tokens', 'N/A')}")
                    print(f"  Total tokens: {usage.get('total_tokens', 'N/A')}")
            else:
                print("\n⚠️  Warning: No 'choices' in response")

    except httpx.HTTPStatusError as e:
        print(f"\n❌ HTTP ERROR: {e.response.status_code}")
        print(f"Response body:")
        print(e.response.text)
    except httpx.RequestError as e:
        print(f"\n❌ REQUEST ERROR: {e}")
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_gemini3_structured_output():
    """Test Gemini 3 with structured JSON output (if supported)"""

    print("\n" + "=" * 80)
    print("TESTING STRUCTURED OUTPUT (JSON MODE)")
    print("=" * 80)

    if not GEMINI_API_KEY:
        print("❌ ERROR: GEMINI_API_KEY not found in .env")
        return

    url = f"{GEMINI_API_BASE}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }

    # Schema for drama structure
    drama_schema = {
        "title": "string",
        "description": "string",
        "characters": [
            {
                "name": "string",
                "description": "string",
                "gender": "string"
            }
        ],
        "episodes": [
            {
                "title": "string",
                "description": "string"
            }
        ]
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert drama writer. Generate drama outlines in JSON format."
            },
            {
                "role": "user",
                "content": f"Generate a drama outline in JSON format matching this schema: {json.dumps(drama_schema)}\n\nDrama premise: A detective discovers their AI assistant has become sentient."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"}  # Request JSON mode
    }

    print(f"\n📤 Testing with response_format: json_object...")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            print(f"Status Code: {response.status_code}")
            response.raise_for_status()

            result = response.json()
            print(f"\n✅ SUCCESS!")

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                print(f"\n📝 GENERATED JSON:")
                print("-" * 80)
                # Try to parse and pretty print the JSON
                try:
                    drama_json = json.loads(content)
                    print(json.dumps(drama_json, indent=2))
                except json.JSONDecodeError:
                    print(content)
                print("-" * 80)

    except httpx.HTTPStatusError as e:
        print(f"\n⚠️  JSON mode not supported or error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"\n⚠️  Error: {e}")


async def main():
    """Run all tests"""

    # Test 1: Basic chat completions
    await test_gemini3_chat_completions()

    # Test 2: Structured output (JSON mode)
    await test_gemini3_structured_output()

    print("\n" + "=" * 80)
    print("TESTS COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
