"""
System prompts and templates for AI generation services.

This module centralizes all system prompts used for:
- Text generation (GPT-5): drama writing, improvement, critique
- Image generation (Gemini): character portraits, drama covers, scenes
- Video generation (Sora): character auditions, scene clips
"""

# =============================================================================
# TEXT GENERATION PROMPTS (GPT-5)
# =============================================================================

def get_drama_generation_system_prompt(episode_guidance: str) -> str:
    """
    System prompt for generating dramas from premise.

    Args:
        episode_guidance: Guidance on number of episodes (e.g., "2-3 episodes for a complete story arc")

    Returns:
        System prompt string
    """
    return f"""You are an expert short-form drama writer. Generate compelling, emotionally engaging dramas based on the user's premise.

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


def get_drama_generation_user_prompt(premise: str, episode_guidance: str) -> str:
    """
    User prompt for generating dramas from premise.

    Args:
        premise: User's drama premise
        episode_guidance: Guidance on number of episodes

    Returns:
        User prompt string
    """
    return f"""Generate a short-form drama based on this premise:

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


DRAMA_IMPROVEMENT_SYSTEM_PROMPT = """You are an expert short-form drama editor. Improve dramas based on user feedback while maintaining the core story.

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


def get_drama_improvement_user_prompt(
    title: str,
    description: str,
    premise: str,
    characters_text: str,
    episodes_text: str,
    feedback: str
) -> str:
    """
    User prompt for improving existing dramas.

    Args:
        title: Drama title
        description: Drama description
        premise: Original premise
        characters_text: Formatted character list
        episodes_text: Formatted episode list
        feedback: User's improvement feedback

    Returns:
        User prompt string
    """
    return f"""Improve this drama based on the feedback:

ORIGINAL DRAMA (High-Level Structure):
Title: {title}
Description: {description}
Premise: {premise}

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


DRAMA_CRITIQUE_SYSTEM_PROMPT = """You are an expert short-form drama critic with deep knowledge of storytelling, character development, pacing, and audience engagement. Your role is to provide constructive, actionable feedback on drama scripts at the high level.

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


def get_drama_critique_user_prompt(
    title: str,
    description: str,
    premise: str,
    characters_text: str,
    episodes_text: str
) -> str:
    """
    User prompt for critiquing dramas.

    Args:
        title: Drama title
        description: Drama description
        premise: Original premise
        characters_text: Formatted character list
        episodes_text: Formatted episode list

    Returns:
        User prompt string
    """
    return f"""Please critique this short-form drama. Focus on the overall narrative structure, character arcs, episode pacing, and storytelling quality at the high level:

DRAMA:
Title: {title}
Description: {description}
Premise: {premise}

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


# =============================================================================
# IMAGE GENERATION PROMPTS (Gemini)
# =============================================================================

def get_character_portrait_prompt(character_description: str, gender: str) -> str:
    """
    Generate prompt for character portrait image.

    Args:
        character_description: Character description
        gender: Character gender

    Returns:
        Full image generation prompt
    """
    character_prompt = f"{character_description}. Gender: {gender}. Show from waist up, facing forward, clear facial features, expressive eyes."

    return f"""Draw this character as a front half-body portrait on the reference image background provided.

CHARACTER: {character_prompt}

STYLE: Anime style, cartoon illustration, vibrant colors, clean lines, detailed character design.
IMPORTANT: If the character description mentions an animal species (like dog, cat, corgi, etc.), draw them as that animal species, NOT as a human. Preserve all species characteristics.

TECHNICAL: Use the EXACT same dimensions and aspect ratio as the reference image. Draw the character portrait on that background, maintaining the vertical 9:16 portrait orientation."""


def get_drama_cover_prompt(title: str, description: str, character_descriptions: str) -> str:
    """
    Generate prompt for drama cover image.

    Args:
        title: Drama title
        description: Drama description
        character_descriptions: Main character descriptions

    Returns:
        Full image generation prompt
    """
    cover_content = f"Create a dramatic cover image for the short-form drama '{title}'. {description}. Feature these main characters: {character_descriptions}. Show them in a dynamic, engaging composition that captures the drama's essence."

    return f"""Draw the drama cover image on the reference image background provided.

DRAMA COVER: {cover_content}

STYLE: Anime style, dramatic composition, vibrant colors, cinematic lighting, eye-catching design suitable for a drama poster.

IMPORTANT: Use the EXACT same dimensions and aspect ratio as the reference image. Create a compelling cover composition on that background, maintaining the vertical 9:16 portrait orientation."""


def get_generic_image_prompt(content_prompt: str) -> str:
    """
    Generate generic image generation prompt with style and technical requirements.

    Args:
        content_prompt: Description of what to generate

    Returns:
        Full image generation prompt
    """
    return f"""CRITICAL REQUIREMENT: STRICT VERTICAL PORTRAIT FORMAT - 9:16 aspect ratio (1080x1920 pixels). The image MUST be taller than it is wide. Vertical orientation is MANDATORY.

IMAGE CONTENT: {content_prompt}

STYLE: Anime style, cartoon illustration, vibrant colors, clean lines."""


# =============================================================================
# VIDEO GENERATION PROMPTS (Sora)
# =============================================================================

def get_character_audition_video_prompt(
    character_name: str,
    character_description: str,
    voice_description: str
) -> str:
    """
    Generate prompt for character audition video.

    Args:
        character_name: Character name
        character_description: Character description
        voice_description: Character voice description

    Returns:
        Video generation prompt
    """
    return f"Character audition video for {character_name}: {character_description}. Voice: {voice_description}. Show the character in a dynamic pose, turning slightly and making expressive gestures that showcase their personality and vocal style. Anime style, smooth animation."


# =============================================================================
# REFERENCE URLS
# =============================================================================

# 9:16 aspect ratio reference image for maintaining portrait orientation
REFERENCE_IMAGE_9_16 = "https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/9_16_reference.jpg"
