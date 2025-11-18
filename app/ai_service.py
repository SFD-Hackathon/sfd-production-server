"""AI service for drama generation using OpenAI GPT-5"""

import os
from typing import Optional
from openai import AsyncOpenAI
from app.models import (
    Drama,
    DramaLite,
    Episode,
    Scene,
    Character,
    Asset,
)


class AIService:
    """Service for AI-powered drama generation"""

    def __init__(self):
        """Initialize AI service with OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE")
        self.model = os.getenv("GPT_MODEL", "gpt-5")

        # Initialize OpenAI client
        client_kwargs = {"api_key": api_key}
        if api_base:
            client_kwargs["base_url"] = api_base

        self.client = AsyncOpenAI(**client_kwargs)

    async def generate_drama(self, premise: str, drama_id: str) -> Drama:
        """
        Generate drama from text premise using GPT-5

        Args:
            premise: Text premise to generate drama from
            drama_id: ID for the generated drama

        Returns:
            Generated Drama object
        """
        system_prompt = """You are an expert short-form drama writer. Generate compelling, emotionally engaging dramas based on the user's premise.

Guidelines:
1. Create 2-3 episodes for a complete story arc
2. Each episode should have 3-5 scenes
3. Create 1-2 main characters (main: true) with depth and clear gender (male/female/other)
4. You may add supporting characters (main: false) but limit total characters to 4-6
5. Include detailed scene descriptions with dialogue
6. CRITICAL: Every scene MUST have exactly 2 assets:
   - One "image" asset for the keyframe/thumbnail (kind: "image", duration: null)
   - One "video" asset for the full animated scene (kind: "video", duration: 10 or 15)
7. Image prompts should describe a single powerful keyframe moment
8. Video prompts should describe the complete scene: camera movements, character actions, dialogue, emotions, and transitions
9. Video duration should be 10 seconds for simple scenes, 15 seconds for more complex scenes with dialogue
10. Make the story emotionally engaging and dramatic
11. Keep scenes concise but impactful (short-form drama style)"""

        user_prompt = f"""Generate a short-form drama based on this premise:

{premise}

Important:
- Create compelling characters and emotional scenes
- CRITICAL: Every scene must have BOTH an image asset AND a video asset (2 assets per scene)
- Image assets are for thumbnails/keyframes (duration: null)
- Video assets are for the full animated scene (duration: 10 or 15 seconds) with detailed prompts
- Use duration 10 for simple scenes, duration 15 for complex scenes with dialogue"""

        try:
            # Call GPT-5 with simplified DramaLite schema
            # Note: GPT-5 only supports temperature=1 (default)
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_completion_tokens=32000,
                response_format=DramaLite,
            )

            # Get parsed DramaLite object
            drama_lite = response.choices[0].message.parsed

            # Convert DramaLite to full Drama with all fields
            drama = self._convert_lite_to_full(drama_lite, drama_id, premise)

            return drama

        except Exception as e:
            print(f"Error generating drama: {e}")
            raise

    def _convert_lite_to_full(self, drama_lite: DramaLite, drama_id: str, premise: str) -> Drama:
        """Convert DramaLite to full Drama model with all required fields"""
        # Convert characters
        characters = [
            Character(
                id=char.id,
                name=char.name,
                description=char.description,
                gender=char.gender,
                main=char.main,
                url=None,
                premise_url=char.premise_url,
                assets=[],
                metadata=None,
            )
            for char in drama_lite.characters
        ]

        # Convert episodes with scenes and assets
        episodes = [
            Episode(
                id=ep.id,
                title=ep.title,
                description=ep.description,
                premise=None,
                url=None,
                scenes=[
                    Scene(
                        id=scene.id,
                        description=scene.description,
                        image_url=None,
                        video_url=None,
                        assets=[
                            Asset(
                                id=asset.id,
                                kind=asset.kind,
                                depends_on=[],
                                prompt=asset.prompt,
                                duration=asset.duration,
                                url=None,
                                metadata=None,
                            )
                            for asset in scene.assets
                        ],
                        metadata=None,
                    )
                    for scene in ep.scenes
                ],
                assets=[],
                metadata=None,
            )
            for ep in drama_lite.episodes
        ]

        # Create full Drama object
        return Drama(
            id=drama_id,
            title=drama_lite.title,
            description=drama_lite.description,
            premise=premise,
            url=None,
            characters=characters,
            episodes=episodes,
            assets=[],
            metadata=None,
        )

    async def improve_drama(self, original_drama: Drama, feedback: str, new_drama_id: str) -> Drama:
        """
        Improve existing drama based on feedback

        Args:
            original_drama: Original drama to improve
            feedback: User feedback for improvement
            new_drama_id: ID for the improved drama

        Returns:
            Improved Drama object
        """
        system_prompt = """You are an expert short-form drama editor. Improve dramas based on user feedback while maintaining the core story."""

        user_prompt = f"""Improve this drama based on the feedback:

ORIGINAL DRAMA:
{original_drama.model_dump_json(indent=2)}

FEEDBACK:
{feedback}

NEW DRAMA ID: {new_drama_id}

Instructions:
1. Keep the original premise and core story
2. Apply the feedback to improve the drama
3. Maintain character consistency
4. Update the drama ID to the new ID provided
5. Ensure every scene has both image and video assets"""

        try:
            # Call GPT-5 with Pydantic structured output
            # Note: GPT-5 only supports temperature=1 (default)
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_completion_tokens=32000,
                response_format=Drama,
            )

            # Get parsed Drama object directly
            drama = response.choices[0].message.parsed

            # Ensure the drama ID matches what was requested
            drama.id = new_drama_id

            return drama

        except Exception as e:
            print(f"Error improving drama: {e}")
            raise


# Global AI service instance (lazy-loaded)
_ai_service = None


def get_ai_service() -> AIService:
    """Get or create the AI service instance (lazy loading)"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
