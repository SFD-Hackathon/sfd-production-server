"""
Configuration for SFD Production Server - Merged Backend
Combines configuration from both ai-short-drama-web-app and sfd-production-server
"""

import os
from dotenv import load_dotenv

# Load .env file ONLY for local development
# On Railway, environment variables are injected directly
if os.getenv('ENVIRONMENT') != 'production':
    load_dotenv(override=True)
    print("🔧 Local development mode: Loading .env file")
else:
    print(f"☁️  Production deployment mode")

# =============================================================================
# API Keys
# =============================================================================

# OpenAI/GPT Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = os.getenv("GPT_MODEL", "gpt-5")

# Google Gemini API (for drama structure generation only)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_DRAMA_MODEL = os.getenv("GEMINI_DRAMA_MODEL", "gemini-3-pro-preview")

# Nano Banana API (for image generation via t8star.cn)
NANO_BANANA_API_KEY = os.getenv("NANO_BANANA_API_KEY")
NANO_BANANA_API_BASE = os.getenv("NANO_BANANA_API_BASE", "https://ai.t8star.cn")

# Sora Configuration (for video generation)
SORA_API_KEY = os.getenv("SORA_API_KEY")
SORA_API_BASE = os.getenv("SORA_API_BASE", "https://ai.t8star.cn")

# =============================================================================
# R2 Storage Configuration
# =============================================================================

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET", "sfd-production")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL")

# Construct R2 endpoint URL
if R2_ACCOUNT_ID:
    R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
else:
    R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")

# =============================================================================
# Authentication
# =============================================================================

# API Keys for authentication (comma-separated list)
API_KEYS_STR = os.getenv("API_KEYS", "")
API_KEYS = [key.strip() for key in API_KEYS_STR.split(",") if key.strip()]

# =============================================================================
# Generation Defaults
# =============================================================================

DEFAULT_ASPECT_RATIO = os.getenv("DEFAULT_ASPECT_RATIO", "9:16")
DEFAULT_VIDEO_DURATION = int(os.getenv("DEFAULT_VIDEO_DURATION", "10"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))  # Number of retries for failed generations

# =============================================================================
# Local Storage Directories
# =============================================================================

JOBS_DIR = os.getenv("JOBS_DIR", "./jobs")
OUTPUTS_DIR = os.getenv("OUTPUTS_DIR", "./outputs")

# =============================================================================
# Server Configuration
# =============================================================================

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
PORT = int(os.getenv("PORT", "8000"))

# =============================================================================
# Validation
# =============================================================================

# Print configuration summary
print("=" * 60)
print("CONFIGURATION SUMMARY:")
print(f"Environment: {ENVIRONMENT}")
print(f"Port: {PORT}")
print(f"GPT Model: {GPT_MODEL}")
print(f"Gemini Drama Model: {GEMINI_DRAMA_MODEL}")
print(f"R2 Bucket: {R2_BUCKET}")
print(f"GEMINI_API_KEY exists: {bool(GEMINI_API_KEY)}")
print(f"NANO_BANANA_API_KEY exists: {bool(NANO_BANANA_API_KEY)}")
print(f"SORA_API_KEY exists: {bool(SORA_API_KEY)}")
print(f"OPENAI_API_KEY exists: {bool(OPENAI_API_KEY)}")
print(f"R2_ACCOUNT_ID exists: {bool(R2_ACCOUNT_ID)}")
print(f"API Keys configured: {len(API_KEYS)}")
print(f"Jobs directory: {JOBS_DIR}")
print(f"Outputs directory: {OUTPUTS_DIR}")
print("=" * 60)

# Validate critical configuration
if not OPENAI_API_KEY:
    print("⚠️  WARNING: OPENAI_API_KEY not found. GPT-based drama generation will not work.")

if not GEMINI_API_KEY:
    print("⚠️  WARNING: GEMINI_API_KEY not found. Image generation will not work.")

if not SORA_API_KEY:
    print("⚠️  WARNING: SORA_API_KEY not found. Video generation will not work.")

if not R2_ACCOUNT_ID or not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
    print("⚠️  WARNING: R2 credentials not complete. Asset storage may not work.")

if not API_KEYS and ENVIRONMENT == "production":
    print("⚠️  WARNING: No API keys configured for authentication.")
