"""Configuration settings for the application"""

from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    environment: str = Field("development", validation_alias="ENVIRONMENT")
    port: int = Field(8000, validation_alias="PORT")
    version: str = "1.0.0"
    
    # OpenAI / GPT
    openai_api_key: Optional[str] = Field(None, validation_alias="OPENAI_API_KEY")
    openai_api_base: Optional[str] = Field(None, validation_alias="OPENAI_API_BASE")
    gpt_model: str = Field("gpt-5", validation_alias="GPT_MODEL")
    
    # Gemini (Image Generation)
    gemini_api_key: Optional[str] = Field(None, validation_alias="GEMINI_API_KEY")
    gemini_api_base: Optional[str] = Field(None, validation_alias="GEMINI_API_BASE")
    gemini_model: str = Field("gemini-2.5-flash-image", validation_alias="GEMINI_MODEL")
    
    # Sora (Video Generation)
    sora_api_key: Optional[str] = Field(None, validation_alias="SORA_API_KEY")
    sora_api_base: Optional[str] = Field(None, validation_alias="SORA_API_BASE")
    sora_model: str = Field("sora-2", validation_alias="SORA_MODEL")
    
    # R2 Storage
    r2_account_id: Optional[str] = Field(None, validation_alias="R2_ACCOUNT_ID")
    r2_access_key_id: Optional[str] = Field(None, validation_alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: Optional[str] = Field(None, validation_alias="R2_SECRET_ACCESS_KEY")
    r2_bucket: str = Field("sfd-production", validation_alias="R2_BUCKET")
    r2_public_url: str = Field("https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev", validation_alias="R2_PUBLIC_URL")
    r2_endpoint_url: Optional[str] = Field(None, validation_alias="R2_ENDPOINT_URL")
    
    # Security
    api_keys: str = Field("", validation_alias="API_KEYS")

    # API Configuration
    api_base_url: str = Field("https://api.shortformdramas.com", validation_alias="API_BASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


def get_settings():
    """Get application settings"""
    return Settings()
