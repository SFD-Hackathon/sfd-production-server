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
11. Keep scenes concise but impactful (short-form drama style)

CHARACTER CONSISTENCY (CRITICAL):
12. For EVERY scene image asset, populate depends_on with character IDs who appear in that scene (max 3 characters)
13. This ensures character visual consistency across scenes
14. Example: If Corgi Musk and Ava appear in a scene, image asset depends_on: ["corgi_musk_id", "ava_id"]
15. For video assets, set depends_on to reference the scene's image asset ID: ["scene_1_img"]
16. Always include at least 1 character reference in scene image assets; use up to 3 if multiple characters present

VOICE CHARACTERIZATION (CRITICAL):
17. For EVERY character, provide a detailed voice_description
18. Include: tone (warm/harsh/soft), pitch (high/low/medium), pace (fast/slow/measured), accent (if any), emotional quality (cheerful/melancholic/stern), speaking style (formal/casual/fragmented)
19. Example: "Warm contralto with slight huskiness, speaks deliberately with pauses, maternal and reassuring tone"
20. Voice should match character personality and background"""

        user_prompt = f"""Generate a short-form drama based on this premise:

{premise}

Important:
- Create compelling characters and emotional scenes
- CRITICAL: Every scene must have BOTH an image asset AND a video asset (2 assets per scene)
- Image assets are for thumbnails/keyframes (duration: null)
- Video assets are for the full animated scene (duration: 10 or 15 seconds) with detailed prompts
- Use duration 10 for simple scenes, duration 15 for complex scenes with dialogue

CHARACTER CONSISTENCY REQUIREMENT:
- For EVERY image asset: Set depends_on to list character IDs appearing in that scene (1-3 characters)
- For EVERY video asset: Set depends_on to reference the scene's image asset ID
- This is CRITICAL for maintaining visual character consistency across the drama

VOICE CHARACTERIZATION REQUIREMENT:
- For EVERY character: Provide detailed voice_description with tone, pitch, pace, accent, emotional quality, and speaking style
- Voice should align with character's personality, age, background, and role in the story
- Be specific and evocative (e.g., "Gravelly bass with Brooklyn accent, speaks in short bursts, sardonic and world-weary")"""

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
                voice_description=char.voice_description,
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
                                depends_on=asset.depends_on,
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
        system_prompt = """You are an expert short-form drama editor. Improve dramas based on user feedback while maintaining the core story.

CHARACTER CONSISTENCY (CRITICAL):
- For EVERY scene image asset, populate depends_on with character IDs who appear in that scene (max 3 characters)
- This ensures character visual consistency across scenes
- For video assets, set depends_on to reference the scene's image asset ID
- Always include at least 1 character reference in scene image assets; use up to 3 if multiple characters present

VOICE CHARACTERIZATION (CRITICAL):
- For EVERY character, provide detailed voice_description with tone, pitch, pace, accent, emotional quality, and speaking style
- Maintain or enhance existing voice descriptions unless feedback specifically requests changes
- Voice should align with character's personality, age, background, and role"""

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
5. Ensure every scene has both image and video assets

CHARACTER CONSISTENCY REQUIREMENT (CRITICAL):
6. For EVERY image asset: Set depends_on to list character IDs appearing in that scene (1-3 characters)
7. For EVERY video asset: Set depends_on to reference the scene's image asset ID
8. This is CRITICAL for maintaining visual character consistency - DO NOT skip this step

VOICE CHARACTERIZATION REQUIREMENT (CRITICAL):
9. For EVERY character: Include detailed voice_description
10. Maintain existing voice descriptions unless feedback requests voice changes
11. If adding new characters, provide comprehensive voice descriptions"""

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

    async def critique_drama(self, drama: Drama) -> str:
        """
        Provide critical feedback on a drama script

        Args:
            drama: Drama to critique

        Returns:
            Critical feedback as a string
        """
        system_prompt = """You are an expert short-form drama critic with deep knowledge of storytelling, character development, pacing, and audience engagement. Your role is to provide constructive, actionable feedback on drama scripts.

Focus on:
1. Story structure and pacing
2. Character development and consistency
3. Dialogue quality and authenticity
4. Emotional impact and engagement
5. Scene composition and flow
6. Overall narrative coherence
7. Strengths and areas for improvement
8. CHARACTER CONSISTENCY: Check that scene image assets reference character IDs via depends_on (1-3 characters per scene) for visual consistency
9. ASSET DEPENDENCIES: Verify video assets reference their scene's image asset ID
10. VOICE CHARACTERIZATION: Evaluate voice descriptions for specificity, appropriateness to character, and distinctiveness across cast

Provide honest, balanced feedback that highlights both what works well and what could be improved."""

        user_prompt = f"""Please critique this short-form drama script. Focus on the narrative, characters, dialogue, and overall storytelling quality:

DRAMA:
Title: {drama.title}
Description: {drama.description}

Characters:
{chr(10).join(f"- {char.id}: {char.name} ({'Main' if char.main else 'Supporting'}, {char.gender}){chr(10)}  Description: {char.description}{chr(10)}  Voice: {char.voice_description}" for char in drama.characters)}

Episodes and Scenes with Assets:
{chr(10).join(f"Episode {i+1}: {ep.title}{chr(10)}{ep.description}{chr(10)}Scenes:{chr(10)}{chr(10).join(f'  Scene {j+1}: {scene.description}{chr(10)}    Assets: {chr(10).join(f\"      - {asset.kind} (id: {asset.id}, depends_on: {asset.depends_on})\" for asset in scene.assets)}' for j, scene in enumerate(ep.scenes))}" for i, ep in enumerate(drama.episodes))}

Provide a comprehensive critique focusing on:
1. Script quality, character development, pacing, and storytelling effectiveness
2. CRITICAL: Verify character consistency - Check that image assets have depends_on referencing character IDs (1-3 per scene)
3. CRITICAL: Verify video assets reference their scene's image asset via depends_on
4. Flag any missing or incorrect asset dependencies as this breaks visual character consistency
5. VOICE EVALUATION: Assess voice_description quality - Are they specific, distinct, and appropriate for each character?"""

        try:
            # Call GPT-5 for critique (using standard completion, not structured output)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_completion_tokens=32000,
            )

            # Get the critique text
            critique = response.choices[0].message.content

            # Handle None case
            if critique is None:
                critique = ""
                print(f"Warning: GPT-5 returned None for critique")

            return critique

        except Exception as e:
            print(f"Error critiquing drama: {e}")
            import traceback
            traceback.print_exc()
            raise


# Global AI service instance (lazy-loaded)
_ai_service = None


def get_ai_service() -> AIService:
    """Get or create the AI service instance (lazy loading)"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
