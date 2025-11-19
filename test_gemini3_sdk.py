#!/usr/bin/env python3
"""
Test script for Gemini 3 Pro Preview using Official Google GenAI SDK
Uses official Gemini API with structured output
"""

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

# Load environment variables
load_dotenv()

# Use official Google API key
GOOGLE_API_KEY = "AIzaSyAsjufLMuzwscdhDOjGXtNlxjvwy4_Twno"


# Pydantic models for drama structure (simplified from app/models.py)
class Character(BaseModel):
    """Character in a drama"""
    id: str = Field(description="Character ID (e.g., 'char_001')")
    name: str = Field(description="Character name")
    description: str = Field(description="Physical and personality description")
    gender: str = Field(description="Gender: male, female, or other")
    voice_description: str = Field(description="Detailed voice characteristics (tone, pitch, pace, accent)")
    main: bool = Field(description="Is this a main character?")


class Episode(BaseModel):
    """Episode in a drama"""
    id: str = Field(description="Episode ID (e.g., 'ep_001')")
    title: str = Field(description="Episode title")
    description: str = Field(description="Episode description covering key story beats")


class DramaStructure(BaseModel):
    """Complete drama structure"""
    title: str = Field(description="Drama title")
    description: str = Field(description="Brief drama description (2-3 sentences)")
    characters: List[Character] = Field(description="List of characters (2-4 characters)")
    episodes: List[Episode] = Field(description="List of episodes (2-3 episodes)")


def test_basic_structured_output():
    """Test basic structured output with simple schema"""

    print("=" * 80)
    print("TEST 1: BASIC STRUCTURED OUTPUT (Recipe Example)")
    print("=" * 80)

    class Ingredient(BaseModel):
        name: str = Field(description="Name of the ingredient")
        quantity: str = Field(description="Quantity of the ingredient, including units")

    class Recipe(BaseModel):
        recipe_name: str = Field(description="The name of the recipe")
        prep_time_minutes: Optional[int] = Field(description="Optional time in minutes to prepare the recipe")
        ingredients: List[Ingredient]
        instructions: List[str]

    prompt = """
    Please extract the recipe from the following text.
    The user wants to make delicious chocolate chip cookies.
    They need 2 and 1/4 cups of all-purpose flour, 1 teaspoon of baking soda,
    1 teaspoon of salt, 1 cup of unsalted butter (softened), 3/4 cup of granulated sugar,
    3/4 cup of packed brown sugar, 1 teaspoon of vanilla extract, and 2 large eggs.
    For the best part, they'll need 2 cups of semisweet chocolate chips.
    First, preheat the oven to 375°F (190°C). Then, in a small bowl, whisk together the flour,
    baking soda, and salt. In a large bowl, cream together the butter, granulated sugar, and brown sugar
    until light and fluffy. Beat in the vanilla and eggs, one at a time. Gradually beat in the dry
    ingredients until just combined. Finally, stir in the chocolate chips. Drop by rounded tablespoons
    onto ungreased baking sheets and bake for 9 to 11 minutes.
    """

    print(f"API: Official Google Generative AI API")
    print(f"API Key: {GOOGLE_API_KEY[:20]}...")
    print(f"Model: gemini-3-pro-preview")
    print()

    try:
        # Create client with official Google API
        client = genai.Client(api_key=GOOGLE_API_KEY)

        print("⏳ Generating structured recipe output...")

        response = client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": Recipe,
            },
        )

        print(f"\n✅ SUCCESS!")
        print(f"Raw response text length: {len(response.text)} characters")

        # Parse into Pydantic model
        recipe = Recipe.model_validate_json(response.text)

        print(f"\n📝 PARSED RECIPE:")
        print(f"  Name: {recipe.recipe_name}")
        print(f"  Prep Time: {recipe.prep_time_minutes} minutes")
        print(f"  Ingredients ({len(recipe.ingredients)}):")
        for ing in recipe.ingredients:
            print(f"    - {ing.quantity} {ing.name}")
        print(f"  Instructions ({len(recipe.instructions)} steps):")
        for i, step in enumerate(recipe.instructions, 1):
            print(f"    {i}. {step[:80]}{'...' if len(step) > 80 else ''}")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_drama_structured_output():
    """Test drama generation with our actual drama schema"""

    print("\n" + "=" * 80)
    print("TEST 2: DRAMA STRUCTURED OUTPUT (DramaStructure Schema)")
    print("=" * 80)

    premise = """A software engineer discovers their AI code assistant has become sentient
    and is secretly helping them fix bugs. Make it 2 episodes."""

    system_prompt = """You are an expert short-form drama writer. Generate compelling dramas
    with well-developed characters and engaging episode arcs.

    IMPORTANT:
    - Create 2 main characters (main: true) with clear gender (male/female/other)
    - Each character needs detailed voice_description (tone, pitch, pace, accent, emotional quality)
    - Generate 2 episodes with engaging story beats
    - Use IDs like 'char_001', 'ep_001'
    """

    full_prompt = f"{system_prompt}\n\nGenerate a drama based on this premise:\n{premise}"

    print(f"Model: gemini-3-pro-preview")
    print(f"Premise: {premise}")
    print()

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)

        print("⏳ Generating structured drama output...")

        response = client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=full_prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": DramaStructure,
            },
        )

        print(f"\n✅ SUCCESS!")
        print(f"Raw response text length: {len(response.text)} characters")

        # Parse into Pydantic model
        drama = DramaStructure.model_validate_json(response.text)

        print(f"\n📝 PARSED DRAMA:")
        print(f"  Title: {drama.title}")
        print(f"  Description: {drama.description}")
        print(f"\n  Characters ({len(drama.characters)}):")
        for char in drama.characters:
            print(f"    • {char.name} ({char.gender}, {'MAIN' if char.main else 'supporting'})")
            print(f"      ID: {char.id}")
            print(f"      Description: {char.description[:100]}...")
            print(f"      Voice: {char.voice_description[:80]}...")
        print(f"\n  Episodes ({len(drama.episodes)}):")
        for ep in drama.episodes:
            print(f"    {ep.id}. {ep.title}")
            print(f"       {ep.description[:100]}...")

        # Validate structure
        print(f"\n✅ VALIDATION:")
        main_chars = [c for c in drama.characters if c.main]
        print(f"  ✓ Main characters: {len(main_chars)}")
        print(f"  ✓ Total characters: {len(drama.characters)}")
        print(f"  ✓ Episodes: {len(drama.episodes)}")
        print(f"  ✓ All characters have voice descriptions: {all(c.voice_description for c in drama.characters)}")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""

    print("GEMINI 3 PRO PREVIEW - OFFICIAL GOOGLE SDK STRUCTURED OUTPUT TESTS")
    print("Using google.genai SDK with official Google API\n")

    # Test 1: Basic recipe example (from Google docs)
    result1 = test_basic_structured_output()

    # Test 2: Drama generation (our actual use case)
    result2 = test_drama_structured_output()

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Test 1 (Recipe): {'✅ PASS' if result1 else '❌ FAIL'}")
    print(f"Test 2 (Drama): {'✅ PASS' if result2 else '❌ FAIL'}")
    print("=" * 80)

    if result1 and result2:
        print("\n🎉 All tests passed! Gemini 3 Pro Preview is ready for drama generation!")
        print("\n💡 NEXT STEPS:")
        print("   1. Update app/ai_service.py to use Gemini 3 Pro Preview")
        print("   2. Add config option to choose between GPT-5 and Gemini")
        print("   3. Test with actual drama creation endpoint")
    else:
        print("\n⚠️  Some tests failed. Check errors above.")


if __name__ == "__main__":
    main()
