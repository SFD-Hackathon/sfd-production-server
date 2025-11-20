"""OpenAI GPT provider for text generation"""

import os
from pydantic import BaseModel
from openai import AsyncOpenAI

from app.providers.base import TextProvider


class OpenAIProvider(TextProvider):
    """OpenAI GPT provider for drama text generation"""

    def __init__(self):
        """Initialize OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE")
        self.model = os.getenv("GPT_MODEL", "gpt-5.1")

        # Initialize OpenAI client
        client_kwargs = {"api_key": api_key}
        if api_base:
            client_kwargs["base_url"] = api_base

        self.client = AsyncOpenAI(**client_kwargs) if api_key else None

    async def generate_structured_output(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel]
    ) -> BaseModel:
        """Generate structured output using GPT"""
        if not self.client:
            raise ValueError("OpenAI client not initialized (OPENAI_API_KEY missing)")

        response = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=response_schema
        )

        return response.choices[0].message.parsed
