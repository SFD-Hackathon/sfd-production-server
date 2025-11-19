"""AI service for drama generation using OpenAI GPT-5 and Google Gemini"""

import os
import re
import base64
import asyncio
import httpx
from typing import Optional, List
from openai import AsyncOpenAI
from google import genai
from google.genai import types
from app.models import (
    Drama,
    DramaLite,
    Episode,
    EpisodeLite,
    Scene,
    Character,
    Asset,
    AssetKind,
)
from app.storage import storage
from app.image_generation import generate_image_async
from app import system_prompts


class AIService:
    """Service for AI-powered drama generation and image generation"""

    def __init__(self):
        """Initialize AI service with OpenAI client and Gemini configuration"""
        # OpenAI/GPT configuration
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE")
        self.gpt_model = os.getenv("GPT_MODEL", "gpt-5.1")

        # Initialize OpenAI client
        client_kwargs = {"api_key": api_key}
        if api_base:
            client_kwargs["base_url"] = api_base

        self.openai_client = AsyncOpenAI(**client_kwargs)

        # Google Gemini configuration for drama generation
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_drama_model = os.getenv("GEMINI_DRAMA_MODEL", "gemini-3-pro-preview")

        # Initialize Gemini client (Google SDK)
        if self.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        else:
            self.gemini_client = None

        # Sora configuration for video generation
        self.sora_api_key = os.getenv("SORA_API_KEY")
        self.sora_api_base = os.getenv("SORA_API_BASE")
        self.sora_model = "sora-2"

    async def generate_drama(self, premise: str, drama_id: str, model: str = "gemini-3-pro-preview") -> Drama:
        """
        Generate drama from text premise using specified AI model

        Args:
            premise: Text premise to generate drama from
            drama_id: ID for the generated drama
            model: AI model to use ('gpt-5.1' or 'gemini-3-pro-preview')

        Returns:
            Generated Drama object
        """
        # Extract episode count from premise if specified (e.g., "10 episodes")
        episode_match = re.search(r'(\d+)\s*episodes?', premise, re.IGNORECASE)
        if episode_match:
            episode_count = int(episode_match.group(1))
            episode_guidance = f"{episode_count} episodes as specified in the premise"
        else:
            episode_count = None
            episode_guidance = "2-3 episodes for a complete story arc"

        # Get prompts from centralized system_prompts module
        system_prompt = system_prompts.get_drama_generation_system_prompt(episode_guidance)
        user_prompt = system_prompts.get_drama_generation_user_prompt(premise, episode_guidance)

        try:
            # Route to appropriate AI model
            if model == "gemini-3-pro-preview":
                drama_lite = await self._generate_with_gemini(system_prompt, user_prompt)
            else:  # gpt-5.1
                drama_lite = await self._generate_with_gpt(system_prompt, user_prompt)

            # Convert DramaLite to full Drama with all fields
            drama = self._convert_lite_to_full(drama_lite, drama_id, premise)

            return drama

        except Exception as e:
            print(f"Error generating drama with {model}: {e}")
            raise

    async def _generate_with_gpt(self, system_prompt: str, user_prompt: str) -> DramaLite:
        """Generate drama using GPT-5.1 (OpenAI)"""
        response = await self.openai_client.beta.chat.completions.parse(
            model=self.gpt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=32000,
            response_format=DramaLite,
        )
        return response.choices[0].message.parsed

    async def _generate_with_gemini(self, system_prompt: str, user_prompt: str) -> DramaLite:
        """Generate drama using Gemini 3 Pro Preview (Google) with low thinking mode"""
        if not self.gemini_client:
            raise ValueError("Gemini client not initialized. Check GEMINI_API_KEY.")

        # Combine system and user prompts for Gemini
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        # Run Gemini generation in thread pool (SDK is sync)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.gemini_client.models.generate_content(
                model=self.gemini_drama_model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DramaLite,
                    thinking_config=types.ThinkingConfig(thinking_level="low")
                ),
            )
        )

        # Parse JSON response into DramaLite
        return DramaLite.model_validate_json(response.text)

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

    async def improve_drama(self, original_drama: Drama, feedback: str, new_drama_id: str, model: str = "gemini-3-pro-preview") -> Drama:
        """
        Improve existing drama based on feedback

        Args:
            original_drama: Original drama to improve
            feedback: User feedback for improvement
            new_drama_id: ID for the improved drama
            model: AI model to use ('gpt-5.1' or 'gemini-3-pro-preview')

        Returns:
            Improved Drama object
        """
        system_prompt = system_prompts.DRAMA_IMPROVEMENT_SYSTEM_PROMPT

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

        # Get user prompt from centralized system_prompts module
        user_prompt = system_prompts.get_drama_improvement_user_prompt(
            title=drama_summary['title'],
            description=drama_summary['description'],
            premise=drama_summary['premise'],
            characters_text=characters_text,
            episodes_text=episodes_text,
            feedback=feedback
        )

        try:
            # Route to appropriate AI model
            if model == "gemini-3-pro-preview":
                drama_lite = await self._generate_with_gemini(system_prompt, user_prompt)
            else:  # gpt-5.1
                drama_lite = await self._generate_with_gpt(system_prompt, user_prompt)

            # Convert to full Drama
            drama = self._convert_lite_to_full(drama_lite, new_drama_id, original_drama.premise)

            return drama

        except Exception as e:
            print(f"Error improving drama with {model}: {e}")
            raise

    async def critique_drama(self, drama: Drama, model: str = "gemini-3-pro-preview") -> str:
        """
        Provide critical feedback on a drama script

        Args:
            drama: Drama to critique
            model: AI model to use ('gpt-5.1' or 'gemini-3-pro-preview')

        Returns:
            Critical feedback as a string
        """
        system_prompt = system_prompts.DRAMA_CRITIQUE_SYSTEM_PROMPT

        # Build formatted lists
        nl = "\n"  # Can't use backslashes in f-string expressions
        characters_text = nl.join(f"- {char.id}: {char.name} ({'Main' if char.main else 'Supporting'}, {char.gender}){nl}  Description: {char.description}{nl}  Voice: {char.voice_description}" for char in drama.characters)
        episodes_text = nl.join(f"Episode {i+1}: {ep.title}{nl}Description: {ep.description}" for i, ep in enumerate(drama.episodes))

        # Get user prompt from centralized system_prompts module
        user_prompt = system_prompts.get_drama_critique_user_prompt(
            title=drama.title,
            description=drama.description,
            premise=drama.premise,
            characters_text=characters_text,
            episodes_text=episodes_text
        )

        try:
            # Route to appropriate AI model
            if model == "gemini-3-pro-preview":
                critique = await self._critique_with_gemini(system_prompt, user_prompt)
            else:  # gpt-5.1
                critique = await self._critique_with_gpt(system_prompt, user_prompt)

            return critique

        except Exception as e:
            print(f"Error critiquing drama with {model}: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def _critique_with_gpt(self, system_prompt: str, user_prompt: str) -> str:
        """Generate critique using GPT-5.1 (OpenAI)"""
        response = await self.openai_client.chat.completions.create(
            model=self.gpt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=32000,
        )
        critique = response.choices[0].message.content
        return critique if critique is not None else ""

    async def _critique_with_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """Generate critique using Gemini 3 Pro Preview (Google) with low thinking mode"""
        if not self.gemini_client:
            raise ValueError("Gemini client not initialized. Check GEMINI_API_KEY.")

        # Combine system and user prompts for Gemini
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        # Run Gemini generation in thread pool (SDK is sync)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.gemini_client.models.generate_content(
                model=self.gemini_drama_model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_level="low")
                ),
            )
        )

        return response.text

    async def _generate_and_upload_image(
        self,
        prompt: str,
        references: List[str],
        upload_key: str,
    ) -> str:
        """
        Helper method to generate image using Gemini and upload to R2.
        Uses consolidated image_generation module with retry logic.

        Args:
            prompt: Full prompt for image generation
            references: List of reference image URLs
            upload_key: R2 key for uploading the image (e.g., "dramas/{id}/cover.png")

        Returns:
            Public R2 URL of the uploaded image
        """
        # Generate image using consolidated async function
        image_bytes = await generate_image_async(
            prompt=prompt,
            reference_images=references if references else None
        )

        # Upload to R2
        storage.s3_client.put_object(
            Bucket=storage.bucket_name,
            Key=upload_key,
            Body=image_bytes,
            ContentType="image/png",
        )

        return f"{storage.public_url_base}/{upload_key}"

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
        # Generate prompt using centralized system_prompts module
        full_prompt = system_prompts.get_character_portrait_prompt(
            character_description=character.description,
            gender=character.gender
        )

        # Build reference list: always include 9:16 reference first
        all_references = [system_prompts.REFERENCE_IMAGE_9_16]
        if references:
            all_references.extend(references)

        # Generate and upload using helper method
        upload_key = f"dramas/{drama_id}/characters/{character.id}.png"
        public_url = await self._generate_and_upload_image(full_prompt, all_references, upload_key)

        # Create and add asset to character (use simple character description for asset prompt)
        character_prompt = f"{character.description}. Gender: {character.gender}. Show from waist up, facing forward, clear facial features, expressive eyes."
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

        # Build character descriptions and generate prompt
        character_descriptions = ", ".join([f"{char.name} ({char.gender}): {char.description}" for char in main_characters])
        full_prompt = system_prompts.get_drama_cover_prompt(
            title=drama.title,
            description=drama.description,
            character_descriptions=character_descriptions
        )

        # Build reference list: always include 9:16 reference first, then character images
        all_references = [system_prompts.REFERENCE_IMAGE_9_16]

        # Add character reference images if available
        for char in main_characters:
            if char.url:
                all_references.append(char.url)

        # Generate and upload using helper method
        upload_key = f"dramas/{drama_id}/cover.png"
        public_url = await self._generate_and_upload_image(full_prompt, all_references, upload_key)

        # Create and add asset to drama (use simple cover description for asset prompt)
        cover_prompt = f"Create a dramatic cover image for the short-form drama '{drama.title}'. {drama.description}. Feature these main characters: {character_descriptions}. Show them in a dynamic, engaging composition that captures the drama's essence."
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

    async def generate_episode_scenes_spec(
        self,
        drama: Drama,
        episode: Episode,
        model: str = "gpt-5"
    ) -> EpisodeLite:
        """
        Generate detailed scene specifications for an episode using existing EpisodeLite model.

        Creates 3-5 scenes with detailed:
        - Scene descriptions
        - Storyboard image prompts
        - Video clip prompts
        - Character dependencies

        Considers overall drama context and previous episodes for continuity.

        Args:
            drama: Full drama object with all episodes and characters
            episode: The episode to generate specs for
            model: AI model to use

        Returns:
            EpisodeLite with populated scenes array containing detailed asset specifications
        """
        # Build context
        character_list = "\n".join([
            f"- {char.name} (ID: {char.id}): {char.description[:100]}..."
            for char in drama.characters
        ])

        # Previous episodes context
        episode_index = next((i for i, ep in enumerate(drama.episodes) if ep.id == episode.id), -1)
        prev_episodes_summary = ""
        if episode_index > 0:
            prev_episodes = drama.episodes[:episode_index]
            prev_episodes_summary = "\n".join([
                f"Ep{i+1} '{ep.title}': {ep.description[:120]}..."
                for i, ep in enumerate(prev_episodes)
            ])

        # System prompt
        system_prompt = f"""You are a visual storytelling director creating detailed scene breakdowns.

DRAMA: {drama.title}
{drama.description}

CHARACTERS (use IDs in depends_on):
{character_list}

PREVIOUS EPISODES:
{prev_episodes_summary or "This is the first episode."}

CURRENT EPISODE: {episode.title}
{episode.description}

Create 3-5 cinematic scenes with 2 assets each (image + video):
- Scene IDs: scene_{episode.id}_01, scene_{episode.id}_02, etc
- Each scene has exactly 2 assets:
  * Asset 1 (image): Storyboard prompt - composition, framing, mood
  * Asset 2 (video): Video clip prompt - 10-15sec action, camera movement
- Use character IDs in asset depends_on (max 3 per scene)
- Ensure visual continuity across scenes"""

        user_prompt = f"Generate detailed scene specs for '{episode.title}'."

        # Use structured output
        if model.startswith("gpt"):
            return await self._generate_episode_spec_with_gpt(system_prompt, user_prompt, episode.id)
        else:
            return await self._generate_episode_spec_with_gemini(system_prompt, user_prompt, episode.id)

    async def _generate_episode_spec_with_gpt(self, system_prompt: str, user_prompt: str, episode_id: str) -> EpisodeLite:
        """Generate using GPT structured output"""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")

        response = await self.openai_client.beta.chat.completions.parse(
            model=self.gpt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=EpisodeLite
        )

        return response.choices[0].message.parsed

    async def _generate_episode_spec_with_gemini(self, system_prompt: str, user_prompt: str, episode_id: str) -> EpisodeLite:
        """Generate using Gemini structured output"""
        if not self.gemini_client:
            raise ValueError("Gemini client not initialized")

        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        response = await asyncio.to_thread(
            lambda: self.gemini_client.models.generate_content(
                model=self.gemini_drama_model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=EpisodeLite
                )
            )
        )

        import json
        spec_dict = json.loads(response.text)
        return EpisodeLite(**spec_dict)

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

        # Generate prompt using centralized system_prompts module
        audition_prompt = system_prompts.get_character_audition_video_prompt(
            character_name=character.name,
            character_description=character.description,
            voice_description=character.voice_description
        )

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
