"""AI service for drama generation using OpenAI GPT-5 and image generation using Gemini"""

import os
import re
import base64
import asyncio
import httpx
from typing import Optional, List
from openai import AsyncOpenAI
from app.models import (
    Drama,
    DramaLite,
    Episode,
    Scene,
    Character,
    Asset,
    AssetKind,
)
from app.storage import storage


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

        # Sora configuration for video generation
        self.sora_api_key = os.getenv("SORA_API_KEY")
        self.sora_api_base = os.getenv("SORA_API_BASE")
        self.sora_model = "sora-2"

    async def generate_drama(self, premise: str, drama_id: str) -> Drama:
        """
        Generate drama from text premise using GPT-5

        Args:
            premise: Text premise to generate drama from
            drama_id: ID for the generated drama

        Returns:
            Generated Drama object
        """
        # Extract episode count from premise if specified (e.g., "10 episodes")
        import re
        episode_match = re.search(r'(\d+)\s*episodes?', premise, re.IGNORECASE)
        if episode_match:
            episode_count = int(episode_match.group(1))
            episode_guidance = f"{episode_count} episodes as specified in the premise"
        else:
            episode_count = None
            episode_guidance = "2-3 episodes for a complete story arc"

        system_prompt = f"""You are an expert short-form drama writer. Generate compelling, emotionally engaging dramas based on the user's premise.

Guidelines:
1. Create {episode_guidance}
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
- Develop a complete story arc across {episode_guidance}
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

        # Build formatted character list
        nl = "\n"  # Can't use backslashes in f-string expressions
        characters_text = nl.join(f"- {char['id']}: {char['name']} ({'Main' if char['main'] else 'Supporting'}, {char['gender']}){nl}  Description: {char['description']}{nl}  Voice: {char['voice_description']}" for char in drama_summary['characters'])
        episodes_text = nl.join(f"{i+1}. {ep['title']}{nl}   {ep['description']}" for i, ep in enumerate(drama_summary['episodes']))

        user_prompt = f"""Improve this drama based on the feedback:

ORIGINAL DRAMA (High-Level Structure):
Title: {drama_summary['title']}
Description: {drama_summary['description']}
Premise: {drama_summary['premise']}

Characters:
{characters_text}

Episodes:
{episodes_text}

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

        # Build formatted lists
        nl = "\n"  # Can't use backslashes in f-string expressions
        characters_text = nl.join(f"- {char.id}: {char.name} ({'Main' if char.main else 'Supporting'}, {char.gender}){nl}  Description: {char.description}{nl}  Voice: {char.voice_description}" for char in drama.characters)
        episodes_text = nl.join(f"Episode {i+1}: {ep.title}{nl}Description: {ep.description}" for i, ep in enumerate(drama.episodes))

        user_prompt = f"""Please critique this short-form drama. Focus on the overall narrative structure, character arcs, episode pacing, and storytelling quality at the high level:

DRAMA:
Title: {drama.title}
Description: {drama.description}
Premise: {drama.premise}

Characters:
{characters_text}

Episodes:
{episodes_text}

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

    async def _generate_and_upload_image(
        self,
        prompt: str,
        references: List[str],
        upload_key: str,
    ) -> str:
        """
        Helper method to generate image using Gemini and upload to R2
        Includes retry logic with up to 2 retries (3 total attempts)

        Args:
            prompt: Full prompt for image generation
            references: List of reference image URLs
            upload_key: R2 key for uploading the image (e.g., "dramas/{id}/cover.png")

        Returns:
            Public R2 URL of the uploaded image
        """
        if not self.gemini_api_key or not self.gemini_api_base:
            raise ValueError(
                "GEMINI_API_KEY and GEMINI_API_BASE environment variables are required"
            )

        # Build request content
        content = [{"type": "text", "text": prompt}]

        # Add reference images
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

        # Retry logic: up to 2 retries (3 total attempts)
        max_retries = 2
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Make async API request
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.gemini_api_base}/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()

                # If we got here, the request succeeded, break out of retry loop
                break

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    print(f"Image generation attempt {attempt + 1} failed: {e}. Retrying...")
                    await asyncio.sleep(2)  # Wait 2 seconds before retry
                else:
                    print(f"Image generation failed after {max_retries + 1} attempts")
                    raise Exception(f"Image generation failed after {max_retries + 1} attempts: {last_error}")

        # Extract image from response
        message = result["choices"][0]["message"]["content"]

        # Check for base64 data URI first (most common)
        data_match = re.search(
            r"(data:image/[^;]+;base64,[A-Za-z0-9+/=]+)", message
        )
        if data_match:
            base64_data = data_match.group(1)
            # Extract base64 content
            header, encoded = base64_data.split(",", 1)
            image_bytes = base64.b64decode(encoded)

            # Upload to R2
            storage.s3_client.put_object(
                Bucket=storage.bucket_name,
                Key=upload_key,
                Body=image_bytes,
                ContentType="image/png",
            )
            return f"{storage.public_url_base}/{upload_key}"

        # Check for markdown image format
        md_match = re.search(r"!\[.*?\]\((https?://[^\)]+)\)", message)
        if md_match:
            return md_match.group(1)

        raise Exception("Could not extract image from response")

    async def generate_character_image(
        self,
        drama_id: str,
        character: Character,
        references: Optional[List[str]] = None,
    ) -> str:
        """
        Generate front half-body character image using Gemini API and upload to R2

        Args:
            drama_id: ID of the drama
            character: Character object with id, description, gender, etc.
            references: Optional list of additional reference image URLs

        Returns:
            Public R2 URL of the uploaded character image
        """
        # Build character-focused prompt using character object
        # Don't assume human - use the full character description which may include species
        character_prompt = f"{character.description}. Gender: {character.gender}. Show from waist up, facing forward, clear facial features, expressive eyes."

        # Explicitly reference the background image for aspect ratio enforcement
        full_prompt = f"""Draw this character as a front half-body portrait on the reference image background provided.

CHARACTER: {character_prompt}

STYLE: Anime style, cartoon illustration, vibrant colors, clean lines, detailed character design.
IMPORTANT: If the character description mentions an animal species (like dog, cat, corgi, etc.), draw them as that animal species, NOT as a human. Preserve all species characteristics.

TECHNICAL: Use the EXACT same dimensions and aspect ratio as the reference image. Draw the character portrait on that background, maintaining the vertical 9:16 portrait orientation."""

        # Build reference list: always include 9:16 reference first
        reference_9_16 = "https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/9_16_reference.jpg"
        all_references = [reference_9_16]
        if references:
            all_references.extend(references)

        # Generate and upload using helper method
        upload_key = f"dramas/{drama_id}/characters/{character.id}.png"
        public_url = await self._generate_and_upload_image(full_prompt, all_references, upload_key)

        # Create and add asset to character
        asset_id = f"{character.id}_portrait_front_halfbody"
        asset = Asset(
            id=asset_id,
            kind=AssetKind.image,
            depends_on=[],
            prompt=character_prompt,
            duration=None,
            url=public_url,
            metadata={"type": "character_portrait", "view": "front", "framing": "half_body"}
        )
        character.assets.append(asset)

        return public_url

    async def generate_drama_cover_image(
        self,
        drama_id: str,
        drama: Drama,
    ) -> str:
        """
        Generate drama cover image featuring main characters using Gemini API and upload to R2

        Args:
            drama_id: ID of the drama
            drama: Drama object with title, description, and characters

        Returns:
            Public R2 URL of the uploaded cover image
        """
        # Get main characters
        main_characters = [char for char in drama.characters if char.main]

        # Build cover image prompt
        character_descriptions = ", ".join([f"{char.name} ({char.gender}): {char.description}" for char in main_characters])
        cover_prompt = f"Create a dramatic cover image for the short-form drama '{drama.title}'. {drama.description}. Feature these main characters: {character_descriptions}. Show them in a dynamic, engaging composition that captures the drama's essence."

        # Explicitly reference the background image for aspect ratio enforcement
        full_prompt = f"""Draw the drama cover image on the reference image background provided.

DRAMA COVER: {cover_prompt}

STYLE: Anime style, dramatic composition, vibrant colors, cinematic lighting, eye-catching design suitable for a drama poster.

IMPORTANT: Use the EXACT same dimensions and aspect ratio as the reference image. Create a compelling cover composition on that background, maintaining the vertical 9:16 portrait orientation."""

        # Build reference list: always include 9:16 reference first, then character images
        reference_9_16 = "https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/9_16_reference.jpg"
        all_references = [reference_9_16]

        # Add character reference images if available
        for char in main_characters:
            if char.url:
                all_references.append(char.url)

        # Generate and upload using helper method
        upload_key = f"dramas/{drama_id}/cover.png"
        public_url = await self._generate_and_upload_image(full_prompt, all_references, upload_key)

        # Create and add asset to drama
        asset_id = f"{drama_id}_cover"
        asset = Asset(
            id=asset_id,
            kind=AssetKind.image,
            depends_on=[char.id for char in main_characters],
            prompt=cover_prompt,
            duration=None,
            url=public_url,
            metadata={"type": "drama_cover", "main_characters": [char.id for char in main_characters]}
        )
        drama.assets.append(asset)

        return public_url

    async def generate_character_audition_video(
        self,
        drama_id: str,
        character: Character,
    ) -> str:
        """
        Generate character audition video using Sora API
        Character audition videos are always 10 seconds long.
        Includes retry logic with up to 2 retries (3 total attempts)

        Args:
            drama_id: ID of the drama
            character: Character object with description, image URL, etc.

        Returns:
            Public R2 URL of the uploaded video
        """
        if not self.sora_api_key or not self.sora_api_base:
            raise ValueError(
                "SORA_API_KEY and SORA_API_BASE environment variables are required"
            )

        # Character audition videos are always 10 seconds
        duration = 10

        # Build character audition prompt including voice description
        audition_prompt = f"Character audition video for {character.name}: {character.description}. Voice: {character.voice_description}. Show the character in a dynamic pose, turning slightly and making expressive gestures that showcase their personality and vocal style. Anime style, smooth animation."

        # Prepare API request
        headers = {
            "Authorization": f"Bearer {self.sora_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "prompt": audition_prompt,
            "model": self.sora_model,
            "aspect_ratio": "9:16",
            "duration": str(duration),
            "hd": False
        }

        # Add character image as reference if available
        if character.url:
            payload["images"] = [character.url]

        # Retry logic: up to 2 retries (3 total attempts)
        max_retries = 2
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Submit video generation job
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.sora_api_base}/v2/videos/generations",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()

                task_id = result.get('task_id')
                if not task_id:
                    raise Exception("No task_id in response")

                print(f"Video generation task created: {task_id} for character {character.name}")

                # Poll for completion (max 10 minutes)
                max_wait = 600
                poll_interval = 5
                elapsed = 0

                while elapsed < max_wait:
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval

                    # Check status
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        status_response = await client.get(
                            f"{self.sora_api_base}/v2/videos/generations/{task_id}",
                            headers=headers,
                        )
                        status_response.raise_for_status()
                        status_result = status_response.json()

                    status = status_result.get('status')
                    print(f"Video generation status for {character.name}: {status} ({elapsed}s)")

                    if status == 'SUCCESS':
                        video_url = status_result['data']['output']
                        print(f"✓ Video generation completed for {character.name}")

                        # Download video and upload to R2
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            video_response = await client.get(video_url)
                            video_response.raise_for_status()
                            video_bytes = video_response.content

                        # Upload to R2
                        upload_key = f"dramas/{drama_id}/characters/{character.id}_audition.mp4"
                        storage.s3_client.put_object(
                            Bucket=storage.bucket_name,
                            Key=upload_key,
                            Body=video_bytes,
                            ContentType="video/mp4",
                        )
                        public_url = f"{storage.public_url_base}/{upload_key}"

                        # Create and add video asset to character
                        asset_id = f"{character.id}_audition_video"

                        # Find the character image asset to set as dependency
                        depends_on = []
                        for existing_asset in character.assets:
                            if existing_asset.kind == AssetKind.image:
                                depends_on.append(existing_asset.id)
                                break

                        asset = Asset(
                            id=asset_id,
                            kind=AssetKind.video,
                            depends_on=depends_on,  # Reference character image asset
                            prompt=audition_prompt,
                            duration=duration,
                            url=public_url,
                            metadata={"type": "character_audition", "duration_seconds": duration}
                        )
                        character.assets.append(asset)

                        return public_url

                    elif status == 'FAILED' or status == 'FAILURE':
                        error = status_result.get('error') or status_result.get('fail_reason', 'Unknown error')
                        raise Exception(f"Video generation failed: {error}")

                    # Continue polling
                    continue

                # Timeout
                raise Exception(f"Video generation timeout after {max_wait}s")

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    print(f"Video generation attempt {attempt + 1} failed for {character.name}: {e}. Retrying...")
                    await asyncio.sleep(3)  # Wait 3 seconds before retry
                else:
                    print(f"Video generation failed after {max_retries + 1} attempts for {character.name}")
                    raise Exception(f"Video generation failed after {max_retries + 1} attempts: {last_error}")


# Global AI service instance (lazy-loaded)
_ai_service = None


def get_ai_service() -> AIService:
    """Get or create the AI service instance (lazy loading)"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
