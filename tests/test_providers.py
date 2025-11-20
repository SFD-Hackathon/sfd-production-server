"""
Test suite for provider modules (Gemini, OpenAI, Sora)

This test suite isolates provider-level API calls to help debug low-level API issues.
Run these tests to verify that provider integrations are working correctly.

Usage:
    pytest tests/test_providers.py -v -s
    pytest tests/test_providers.py::TestGeminiProvider -v -s
    pytest tests/test_providers.py::TestGeminiProvider::test_generate_image -v -s
"""

import pytest
import asyncio
import os
from typing import Optional

# Import providers
from app.providers.gemini_provider import GeminiProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.sora_provider import SoraProvider


class TestGeminiProvider:
    """Test Gemini provider for text and image generation"""

    @pytest.fixture
    def provider(self):
        """Create Gemini provider instance"""
        return GeminiProvider()

    @pytest.mark.asyncio
    async def test_generate_image_simple(self, provider):
        """Test basic image generation without reference images"""
        prompt = "A cute cartoon dog sitting in a park, anime style, vibrant colors"

        print(f"\n🎨 Testing Gemini image generation...")
        print(f"Prompt: {prompt}")

        # Generate image
        image_bytes = await provider.generate_image(prompt=prompt, reference_images=None)

        # Verify we got bytes back
        assert isinstance(image_bytes, bytes), "Expected bytes object"
        assert len(image_bytes) > 0, "Image bytes should not be empty"

        print(f"✓ Image generated successfully ({len(image_bytes)} bytes)")

    @pytest.mark.asyncio
    async def test_generate_image_with_reference(self, provider):
        """Test image generation with reference image (9:16 aspect ratio)"""
        prompt = "A brave warrior character, front half-body portrait, anime style"
        reference_image = "https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/9_16_reference.jpg"

        print(f"\n🎨 Testing Gemini image generation with reference...")
        print(f"Prompt: {prompt}")
        print(f"Reference: {reference_image}")

        # Generate image
        image_bytes = await provider.generate_image(
            prompt=prompt,
            reference_images=[reference_image]
        )

        # Verify we got bytes back
        assert isinstance(image_bytes, bytes), "Expected bytes object"
        assert len(image_bytes) > 0, "Image bytes should not be empty"

        print(f"✓ Image generated with reference ({len(image_bytes)} bytes)")

    @pytest.mark.asyncio
    async def test_generate_image_retry_logic(self, provider):
        """Test that retry logic works when API fails"""
        # Use an invalid prompt or reference to trigger retry
        prompt = ""  # Empty prompt might cause failure

        print(f"\n🔄 Testing Gemini retry logic...")

        try:
            image_bytes = await provider.generate_image(
                prompt=prompt,
                reference_images=None,
                max_retries=2
            )
            # If it succeeds despite empty prompt, that's okay
            print(f"✓ Request succeeded (no retry needed)")
        except Exception as e:
            # Verify it attempted retries
            print(f"✓ Request failed as expected: {str(e)}")
            assert "attempt" in str(e).lower() or "failed" in str(e).lower()

    @pytest.mark.asyncio
    async def test_text_generation_structured(self, provider):
        """Test structured text generation using Gemini"""
        from pydantic import BaseModel

        class SimpleResponse(BaseModel):
            title: str
            description: str

        system_prompt = "You are a creative assistant that generates drama titles and descriptions."
        user_prompt = "Create a short drama about a dog detective"

        print(f"\n📝 Testing Gemini structured text generation...")

        # Skip if text API not configured
        if not provider.text_client:
            pytest.skip("GEMINI_API_KEY not configured")

        response = await provider.generate_structured_output(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=SimpleResponse
        )

        assert isinstance(response, SimpleResponse)
        assert len(response.title) > 0
        assert len(response.description) > 0

        print(f"✓ Generated: {response.title}")
        print(f"  Description: {response.description[:100]}...")

    def test_provider_initialization(self, provider):
        """Test that provider initializes with correct configuration"""
        print(f"\n⚙️  Testing Gemini provider initialization...")

        assert provider.image_api_key is not None, "NANO_BANANA_API_KEY must be set"
        assert provider.image_api_base is not None, "Image API base must be set"
        assert provider.image_model == "gemini-2.5-flash-image"

        print(f"✓ Image API Base: {provider.image_api_base}")
        print(f"✓ Image Model: {provider.image_model}")
        print(f"✓ Text Model: {provider.text_model}")


class TestOpenAIProvider:
    """Test OpenAI provider for text generation"""

    @pytest.fixture
    def provider(self):
        """Create OpenAI provider instance"""
        return OpenAIProvider()

    def test_provider_initialization(self, provider):
        """Test that provider initializes correctly"""
        print(f"\n⚙️  Testing OpenAI provider initialization...")

        if not provider.client:
            pytest.skip("OPENAI_API_KEY not configured")

        assert provider.model is not None
        print(f"✓ Model: {provider.model}")

    @pytest.mark.asyncio
    async def test_text_generation_structured(self, provider):
        """Test structured text generation using OpenAI"""
        from pydantic import BaseModel

        class SimpleResponse(BaseModel):
            title: str
            summary: str

        system_prompt = "You are a helpful assistant that creates drama summaries."
        user_prompt = "Create a title and summary for a drama about a detective cat"

        print(f"\n📝 Testing OpenAI structured text generation...")

        if not provider.client:
            pytest.skip("OPENAI_API_KEY not configured")

        response = await provider.generate_structured_output(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=SimpleResponse
        )

        assert isinstance(response, SimpleResponse)
        assert len(response.title) > 0
        assert len(response.summary) > 0

        print(f"✓ Generated: {response.title}")
        print(f"  Summary: {response.summary[:100]}...")


class TestSoraProvider:
    """Test Sora provider for video generation"""

    @pytest.fixture
    def provider(self):
        """Create Sora provider instance"""
        return SoraProvider()

    def test_provider_initialization(self, provider):
        """Test that provider initializes correctly"""
        print(f"\n⚙️  Testing Sora provider initialization...")

        assert provider.api_key is not None, "SORA_API_KEY must be set"
        assert provider.api_base is not None, "Sora API base must be set"

        print(f"✓ API Base: {provider.api_base}")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_generate_video_simple(self, provider):
        """Test basic video generation (slow - can take 1-2 minutes)"""
        prompt = "A cartoon dog running happily in a park, anime style, smooth animation"
        duration = 5  # 5 seconds for faster test

        print(f"\n🎬 Testing Sora video generation (this may take 1-2 minutes)...")
        print(f"Prompt: {prompt}")
        print(f"Duration: {duration}s")

        # Generate video
        video_url = await provider.generate_video(
            prompt=prompt,
            duration=duration
        )

        # Verify we got a URL back
        assert isinstance(video_url, str), "Expected string URL"
        assert len(video_url) > 0, "Video URL should not be empty"
        assert video_url.startswith("http"), "Should be a valid URL"

        print(f"✓ Video generated successfully: {video_url}")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_generate_video_with_reference(self, provider):
        """Test video generation with reference image (slow)"""
        prompt = "Character walking forward confidently, anime style"
        duration = 5
        reference_image = "https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/dramas/test_drama/characters/test_char.png"

        print(f"\n🎬 Testing Sora video generation with reference...")
        print(f"Prompt: {prompt}")
        print(f"Reference: {reference_image}")

        # Note: Sora provider might not support reference images - check implementation
        try:
            video_url = await provider.generate_video(
                prompt=prompt,
                duration=duration,
                reference_image=reference_image
            )
            print(f"✓ Video generated with reference: {video_url}")
        except TypeError:
            print(f"⚠️  Sora provider doesn't support reference_image parameter")
            pytest.skip("Reference image not supported by current Sora implementation")


class TestProviderPerformance:
    """Performance tests for providers"""

    @pytest.mark.asyncio
    async def test_gemini_image_generation_speed(self):
        """Test that Gemini image generation completes within reasonable time"""
        import time

        provider = GeminiProvider()
        prompt = "A simple test image, cartoon style"

        print(f"\n⏱️  Testing Gemini image generation speed...")

        start_time = time.time()
        image_bytes = await provider.generate_image(prompt=prompt)
        duration = time.time() - start_time

        print(f"✓ Generation completed in {duration:.2f}s")

        # Should complete in under 30 seconds for simple images
        assert duration < 30, f"Image generation took too long: {duration:.2f}s"

    @pytest.mark.asyncio
    async def test_concurrent_image_generation(self):
        """Test multiple concurrent image generations"""
        provider = GeminiProvider()

        prompts = [
            "A red apple, simple cartoon",
            "A blue car, simple cartoon",
            "A green tree, simple cartoon",
        ]

        print(f"\n🚀 Testing concurrent image generation...")
        print(f"Generating {len(prompts)} images in parallel...")

        # Generate all images concurrently
        tasks = [provider.generate_image(prompt=p) for p in prompts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check results
        successful = sum(1 for r in results if isinstance(r, bytes))
        failed = sum(1 for r in results if isinstance(r, Exception))

        print(f"✓ Completed: {successful} successful, {failed} failed")

        assert successful > 0, "At least one image should succeed"


# Test configuration
def pytest_configure(config):
    """Add custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


if __name__ == "__main__":
    """Run tests directly"""
    pytest.main([__file__, "-v", "-s"])
