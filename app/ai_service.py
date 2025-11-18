"""AI service for drama generation using OpenAI GPT-5"""

import os
import json
from typing import Optional
from openai import AsyncOpenAI
from app.models import Drama


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

Output ONLY valid JSON matching this exact schema (no markdown, no explanations):

{
  "id": "drama_id_here",
  "title": "Drama Title",
  "description": "Brief description",
  "premise": "Original premise",
  "url": null,
  "characters": [
    {
      "id": "char_001",
      "name": "Character Name",
      "description": "Character description with personality and background",
      "url": null,
      "premise_url": null,
      "assets": [],
      "metadata": null
    }
  ],
  "episodes": [
    {
      "id": "ep_001",
      "title": "Episode Title",
      "description": "Episode description",
      "premise": null,
      "url": null,
      "scenes": [
        {
          "id": "scene_001",
          "description": "Detailed scene description with action and dialogue",
          "image_url": null,
          "video_url": null,
          "assets": [
            {
              "id": "asset_001",
              "kind": "image",
              "depends_on": [],
              "prompt": "Detailed image generation prompt",
              "duration": null,
              "url": null,
              "metadata": null
            }
          ],
          "metadata": null
        }
      ],
      "assets": [],
      "metadata": null
    }
  ],
  "assets": [],
  "metadata": null
}

Guidelines:
1. Create 2-3 episodes for a complete story arc
2. Each episode should have 3-5 scenes
3. Develop 2-4 main characters with depth
4. Include detailed scene descriptions with dialogue
5. Generate image prompts for key visual moments
6. Make the story emotionally engaging and dramatic
7. Keep scenes concise but impactful (short-form drama style)
"""

        user_prompt = f"""Generate a short-form drama based on this premise:

{premise}

Remember:
- Output ONLY valid JSON (no markdown code blocks)
- Use the drama ID: {drama_id}
- Include the original premise in the output
- Create compelling characters and emotional scenes
- Generate detailed image prompts for visual assets"""

        try:
            # Call GPT-5 with structured output
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_completion_tokens=32000,
                response_format={"type": "json_object"},
            )

            # Parse response
            drama_json = response.choices[0].message.content
            drama_data = json.loads(drama_json)

            # Validate and create Drama object
            return Drama(**drama_data)

        except Exception as e:
            print(f"Error generating drama: {e}")
            raise

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

Output ONLY valid JSON matching the drama schema (no markdown, no explanations)."""

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
5. Output ONLY valid JSON"""

        try:
            # Call GPT-5
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_completion_tokens=32000,
                response_format={"type": "json_object"},
            )

            # Parse response
            drama_json = response.choices[0].message.content
            drama_data = json.loads(drama_json)

            # Validate and create Drama object
            return Drama(**drama_data)

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
