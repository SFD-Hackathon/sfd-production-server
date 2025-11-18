"""AI service for drama generation using OpenAI GPT-5 and image generation using Gemini"""

import os
import re
import base64
import requests
from typing import Optional, List
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
    """Service for AI-powered drama generation and image generation"""

    def __init__(self):
        """Initialize AI service with OpenAI client and Gemini configuration"""
        # OpenAI/GPT configuration
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE")
        self.model = os.getenv("GPT_MODEL", "gpt-5")

        # Initialize OpenAI client
        client_kwargs = {"api_key": api_key}
        if api_base:
            client_kwargs["base_url"] = api_base

        self.client = AsyncOpenAI(**client_kwargs)

        # Gemini configuration for image generation
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_api_base = os.getenv("GEMINI_API_BASE")
        self.gemini_model = "gemini-2.5-flash-image"

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
2. Create 1-2 main characters (main: true) with depth and clear gender (male/female/other)
3. You may add supporting characters (main: false) but limit total characters to 4-6
4. Focus on episode-level narrative structure and story beats
5. Each episode description should cover the full episode arc with key story developments
6. Make the story emotionally engaging and dramatic

VOICE CHARACTERIZATION (CRITICAL):
7. For EVERY character, provide a detailed voice_description
8. Include: tone (warm/harsh/soft), pitch (high/low/medium), pace (fast/slow/measured), accent (if any), emotional quality (cheerful/melancholic/stern), speaking style (formal/casual/fragmented)
9. Example: "Warm contralto with slight huskiness, speaks deliberately with pauses, maternal and reassuring tone"
10. Voice should match character personality and background

Note: Scenes and assets will be generated in a later processing step. Focus on the high-level drama structure, character development, and episode narrative arcs."""

        user_prompt = f"""Generate a short-form drama based on this premise:

{premise}

Important:
- Create compelling characters with depth and clear motivations
- Develop a complete story arc across 2-3 episodes
- Each episode description should detail the key story beats, character developments, and emotional moments
- Focus on narrative structure at the episode level

VOICE CHARACTERIZATION REQUIREMENT:
- For EVERY character: Provide detailed voice_description with tone, pitch, pace, accent, emotional quality, and speaking style
- Voice should align with character's personality, age, background, and role in the story
- Be specific and evocative (e.g., "Gravelly bass with Brooklyn accent, speaks in short bursts, sardonic and world-weary")

Scenes and visual assets will be generated separately in a later step."""

        try:
            # Call GPT-5 with DramaLite schema (episode-level only, no scenes)
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

            # Get parsed DramaLite object (episodes without scenes)
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

        # Convert episodes (with or without scenes)
        episodes = [
            Episode(
                id=ep.id,
                title=ep.title,
                description=ep.description,
                premise=None,  # Premise is for human input, not AI-generated
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
                ] if ep.scenes else [],  # Handle empty scenes list
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

Focus on:
1. High-level narrative structure and episode arcs
2. Character development and consistency
3. Episode pacing and story beats
4. Overall dramatic impact and emotional resonance

VOICE CHARACTERIZATION (CRITICAL):
- For EVERY character, provide detailed voice_description with tone, pitch, pace, accent, emotional quality, and speaking style
- Maintain or enhance existing voice descriptions unless feedback specifically requests changes
- Voice should align with character's personality, age, background, and role

Note: Focus on drama, character, and episode levels. Scenes and assets will be handled in a later processing step."""

        # Create simplified drama summary for the prompt
        drama_summary = {
            "title": original_drama.title,
            "description": original_drama.description,
            "premise": original_drama.premise,
            "characters": [
                {
                    "id": char.id,
                    "name": char.name,
                    "description": char.description,
                    "gender": char.gender,
                    "voice_description": char.voice_description,
                    "main": char.main,
                }
                for char in original_drama.characters
            ],
            "episodes": [
                {
                    "id": ep.id,
                    "title": ep.title,
                    "description": ep.description,
                }
                for ep in original_drama.episodes
            ],
        }

        user_prompt = f"""Improve this drama based on the feedback:

ORIGINAL DRAMA (High-Level Structure):
Title: {drama_summary['title']}
Description: {drama_summary['description']}
Premise: {drama_summary['premise']}

Characters:
{chr(10).join(f"- {char['id']}: {char['name']} ({'Main' if char['main'] else 'Supporting'}, {char['gender']}){chr(10)}  Description: {char['description']}{chr(10)}  Voice: {char['voice_description']}" for char in drama_summary['characters'])}

Episodes:
{chr(10).join(f"{i+1}. {ep['title']}{chr(10)}   {ep['description']}" for i, ep in enumerate(drama_summary['episodes']))}

FEEDBACK:
{feedback}

Instructions:
1. Keep the original premise and core story
2. Apply the feedback to improve the drama structure, character development, and episode arcs
3. Maintain character consistency and voice descriptions
4. Focus on episode-level narrative improvements
5. Each episode description should detail the key story beats and character developments

VOICE CHARACTERIZATION REQUIREMENT:
- For EVERY character: Include detailed voice_description
- Maintain existing voice descriptions unless feedback requests voice changes
- If adding new characters, provide comprehensive voice descriptions

Scenes and visual assets will be generated in a later step. Focus on the high-level drama structure."""

        try:
            # Call GPT-5 with DramaLite (episode-level only)
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

            # Get parsed DramaLite object (episodes without scenes)
            drama_lite = response.choices[0].message.parsed

            # Convert to full Drama
            drama = self._convert_lite_to_full(drama_lite, new_drama_id, original_drama.premise)

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
        system_prompt = """You are an expert short-form drama critic with deep knowledge of storytelling, character development, pacing, and audience engagement. Your role is to provide constructive, actionable feedback on drama scripts at the high level.

Focus on:
1. Overall story structure and narrative arc
2. Episode pacing and story progression
3. Character development, depth, and consistency across episodes
4. Character motivations and believability
5. Emotional impact and dramatic tension
6. Episode-to-episode flow and coherence
7. Strengths and areas for improvement
8. VOICE CHARACTERIZATION: Evaluate voice descriptions for specificity, appropriateness to character, and distinctiveness across cast

Provide honest, balanced feedback that highlights both what works well and what could be improved. Focus on the high-level drama structure - scenes and visual assets will be evaluated separately."""

        user_prompt = f"""Please critique this short-form drama. Focus on the overall narrative structure, character arcs, episode pacing, and storytelling quality at the high level:

DRAMA:
Title: {drama.title}
Description: {drama.description}
Premise: {drama.premise}

Characters:
{chr(10).join(f"- {char.id}: {char.name} ({'Main' if char.main else 'Supporting'}, {char.gender}){chr(10)}  Description: {char.description}{chr(10)}  Voice: {char.voice_description}" for char in drama.characters)}

Episodes:
{chr(10).join(f"Episode {i+1}: {ep.title}{chr(10)}Description: {ep.description}" for i, ep in enumerate(drama.episodes))}

Provide a comprehensive critique focusing on:
1. Overall story structure and narrative coherence
2. Character development and consistency across episodes
3. Episode pacing and progression
4. Emotional impact and dramatic effectiveness
5. VOICE EVALUATION: Assess voice_description quality - Are they specific, distinct, and appropriate for each character?
6. Suggestions for improving the high-level drama structure

Note: This critique focuses on the drama, character, and episode levels. Scene-level details will be evaluated separately."""

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

    def generate_image(
        self,
        prompt: str,
        references: Optional[List[str]] = None,
        asset_id: Optional[str] = None,
    ) -> str:
        """
        Generate an image using Gemini API

        Args:
            prompt: Text prompt for image generation
            references: Optional list of additional reference image URLs
            asset_id: Optional asset ID for context

        Returns:
            Image URL (markdown format) or base64 data URI

        Note: Always generates 9:16 aspect ratio images with a standard reference
        """
        if not self.gemini_api_key or not self.gemini_api_base:
            raise ValueError(
                "GEMINI_API_KEY and GEMINI_API_BASE environment variables are required"
            )

        # Hard-coded 9:16 aspect ratio
        aspect_ratio = "9:16"
        aspect_directive = f"ASPECT RATIO MUST BE {aspect_ratio} (width:height)"

        # Put aspect ratio requirement at the beginning AND end for emphasis
        full_prompt = f"CRITICAL REQUIREMENT: {aspect_directive}\n\nIMAGE CONTENT: {prompt}\n\nSTYLE: Anime style, cartoon illustration, vibrant colors, clean lines.\n\nREMINDER: {aspect_directive}"

        # Build request content with text prompt
        content = [{"type": "text", "text": full_prompt}]

        # Always include 9:16 reference image first
        reference_9_16 = "https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/9_16_reference.jpg"
        content.append({"type": "image_url", "image_url": {"url": reference_9_16}})

        # Add any additional references
        if references:
            for ref in references:
                content.append({"type": "image_url", "image_url": {"url": ref}})

        # Build API request payload
        payload = {
            "model": self.gemini_model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.gemini_api_key}",
            "Content-Type": "application/json",
        }

        # Make API request
        response = requests.post(
            f"{self.gemini_api_base}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()

        # Extract image from response
        message = result["choices"][0]["message"]["content"]

        # Check for markdown image format
        md_match = re.search(r"!\[.*?\]\((https?://[^\)]+)\)", message)
        if md_match:
            return md_match.group(1)

        # Check for base64 data URI
        data_match = re.search(
            r"(data:image/[^;]+;base64,[A-Za-z0-9+/=]+)", message
        )
        if data_match:
            return data_match.group(1)

        raise Exception("Could not extract image from response")


# Global AI service instance (lazy-loaded)
_ai_service = None


def get_ai_service() -> AIService:
    """Get or create the AI service instance (lazy loading)"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
