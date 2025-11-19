# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI-based Drama Generation API with GPT-5 integration for generating AI-powered short-form dramas. Deployed on Railway with Cloudflare R2 storage backend.

**Tech Stack**: Python 3.11+, FastAPI, OpenAI GPT-5, Gemini (image gen), Sora (video gen), R2 (storage), Railway (hosting)

## Development Commands

### Local Development
```bash
# Setup environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run server (development mode with auto-reload)
python main.py
# OR
uvicorn main:app --reload --port 8000

# Access API
# - API: http://localhost:8000
# - Swagger Docs: http://localhost:8000/docs
# - OpenAPI Schema: http://localhost:8000/openapi.json
```

### Testing
```bash
# No pytest setup currently - use manual testing via test_api.py or Swagger
python test_api.py
```

### Code Quality
```bash
# Format code
pip install black isort
black .
isort .
```

## High-Level Architecture

### Request Flow for Drama Generation

1. **Client request** → `/dramas` (POST with premise)
2. **API creates job** → Returns `202 Accepted` with `jobId` immediately
3. **Background task** → Async drama generation (30-60s)
   - GPT-5 generates drama structure (episodes, characters)
   - Gemini generates character images (parallel)
   - Gemini generates drama cover image
   - Sora generates character audition videos (optional)
4. **Storage** → Drama saved to R2 as JSON
5. **Client polls** → `/dramas/{dramaId}/jobs/{jobId}` to check status
6. **Job completes** → Status changes to `completed`, client fetches drama

### Core Components

**main.py**: FastAPI app entry point, CORS setup, router registration, lifespan management

**app/config.py**: Centralized configuration using Pydantic Settings. All env vars loaded here (OpenAI, Gemini, Sora, R2 credentials).

**app/models.py**: Pydantic models for all entities (Drama, Episode, Scene, Character, Asset). Two-tier model system:
- `DramaLite`: Used by GPT-5 for initial generation (episodes only, no scenes)
- `Drama`: Full model with all nested entities including scenes and assets

**app/storage.py**: R2 Storage client (S3-compatible via boto3)
- Drama persistence: `dramas/{drama_id}/drama.json`
- Images: `dramas/{drama_id}/characters/{character_id}.png`
- Videos: `dramas/{drama_id}/characters/{character_id}_audition.mp4`
- **Optimistic locking**: Hash-based conflict detection to prevent lost updates during concurrent modifications
- **Warning**: `list_dramas()` is inefficient - fetches/parses every JSON file. Use database for production scale.

**app/ai_service.py**: AI generation orchestration
- `generate_drama()`: GPT-5 structured output → DramaLite → Drama conversion
- `improve_drama()`: Takes feedback, regenerates with GPT-5
- `generate_character_image()`: Gemini API with 9:16 aspect ratio, includes retry logic (3 attempts)
- `generate_character_audition_video()`: Sora API for 10s videos, includes retry logic (3 attempts)
- `critique_drama()`: GPT-5 text critique for quality feedback
- **Two-phase generation**: Episode-level structure first, scene-level details later (reduces token usage)

**app/job_manager.py**: In-memory job tracking (JobManager singleton)
- Status flow: `pending` → `processing` → `completed`/`failed`
- **Limitation**: Jobs lost on server restart (not persisted to storage)
- For production: Consider Redis or database for job persistence

**app/dependencies.py**: API key authentication middleware
- Validates `X-API-Key` header against `API_KEYS` env var (comma-separated)
- If `API_KEYS` is empty, authentication is disabled (for development)

### Routers (API Endpoints)

All routers follow RESTful patterns with nested resources:

**app/routers/dramas.py**: Core drama CRUD + async generation
- `POST /dramas` - Create from premise (async job) or JSON (sync)
- `GET /dramas` - List with pagination (cursor-based)
- `GET /dramas/{id}` - Get single drama
- `PATCH /dramas/{id}` - Update drama properties
- `DELETE /dramas/{id}` - Delete drama + all assets
- `POST /dramas/{id}/improve` - Improve with feedback (async job)
- `POST /dramas/{id}/critique` - Get AI critique (async job)

**app/routers/jobs.py**: Job status tracking
- `GET /dramas/{dramaId}/jobs/{jobId}` - Get job status
- `GET /dramas/{dramaId}/jobs` - List all jobs for drama

**app/routers/characters.py, episodes.py, scenes.py, assets.py**: Nested resource management
- GET/PATCH operations for individual entities within dramas
- Follow pattern: `/dramas/{dramaId}/[episodes/{episodeId}/]entity`

### Storage Architecture Patterns

**Optimistic Locking Pattern** (storage.py:79-108):
- Compute SHA256 hash of drama JSON before modification
- On save, verify hash matches current stored version
- Raises `StorageConflictError` if concurrent modification detected
- Used in drama generation to protect against race conditions

**Reload-Append-Save Pattern** (storage.py:280-318):
- Reload fresh drama from storage
- Append new entity (e.g., asset to character)
- Save updated drama
- Simple pattern for non-critical operations where last-write-wins is acceptable

**Full Job Execution Protection** (routers/dramas.py:73-100):
- Get initial hash before starting job
- Perform all AI operations (generation, image creation)
- Save with hash verification at the end
- Protects entire job execution from concurrent modifications

### Voice Characterization System

All characters must have detailed `voice_description` fields:
- **Purpose**: Enable high-quality text-to-speech generation
- **Format**: tone, pitch, pace, accent, emotional quality, speaking style
- **Example**: "Warm contralto with slight huskiness, speaks deliberately with pauses, maternal and reassuring tone"
- GPT-5 prompts explicitly require voice descriptions for every character
- Used in character audition videos and future TTS generation

## Environment Variables

**Required for core functionality:**
- `OPENAI_API_KEY` - OpenAI API key with GPT-5 access
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` - R2 credentials
- `R2_BUCKET` - R2 bucket name (default: sfd-production)

**Optional for extended features:**
- `GEMINI_API_KEY`, `GEMINI_API_BASE` - For character image generation
- `SORA_API_KEY`, `SORA_API_BASE` - For character video generation
- `API_KEYS` - Comma-separated API keys (empty = no auth)
- `GPT_MODEL` - Model name (default: gpt-5)
- `ENVIRONMENT` - development/production (affects reload behavior)
- `PORT` - Server port (default: 8000)

See `.env.example` for complete list.

## Key Implementation Details

### Drama Generation Flow
1. Client sends premise → `CreateFromPremise` model
2. FastAPI queues background task → returns `202 Accepted` with job ID
3. Background task:
   - Calls GPT-5 with DramaLite schema (episode-level only)
   - Converts DramaLite → Drama with empty scenes lists
   - Saves drama to R2 (first checkpoint)
   - Generates character images in parallel (Gemini)
   - Generates drama cover image (Gemini)
   - Updates drama with image URLs
   - Saves final drama to R2 with hash verification
   - Marks job as `completed`
4. Client polls job status endpoint until `completed`
5. Client fetches final drama

### Conflict Detection Strategy
**Problem**: Multiple concurrent processes modifying the same drama can cause lost updates.

**Solution**: Hash-based optimistic locking
- Compute SHA256 hash of drama JSON
- Pass `expected_hash` to `save_drama()`
- Storage verifies current hash matches expected hash
- Raises `StorageConflictError` if mismatch detected

**When to use**:
- Full job execution protection: Get hash at start, verify at end
- Critical updates: Updates that must not be lost
- Skip for non-critical operations where last-write-wins is acceptable

### Image Generation Constraints
- **Aspect ratio**: Always 9:16 (vertical portrait) enforced via reference image
- **Reference image**: `https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev/9_16_reference.jpg`
- **Character images**: Front half-body portraits, anime style
- **Retry logic**: 3 total attempts (initial + 2 retries) with 2s delay between attempts

### Video Generation Constraints
- **Duration**: Character auditions are always 10 seconds
- **Aspect ratio**: 9:16 (vertical)
- **Polling**: Status checked every 5s, max 10 minutes timeout
- **Retry logic**: 3 total attempts (initial + 2 retries) with 3s delay between attempts

## Common Development Patterns

### Adding a New Endpoint
1. Define request/response models in `app/models.py`
2. Add route handler in appropriate router file
3. Add authentication dependency if needed: `api_key: str = Depends(get_api_key)`
4. Use storage methods for persistence: `await storage.get_drama(drama_id)`
5. Test via Swagger UI at `/docs`

### Modifying Drama Structure
1. Update Pydantic models in `app/models.py`
2. Update GPT-5 prompts in `app/ai_service.py` if schema changes
3. Test with `CreateFromPremise` to ensure GPT-5 generates correct structure
4. Update conversion logic in `_convert_lite_to_full()` if needed

### Adding New AI Features
1. Add method to `AIService` class in `app/ai_service.py`
2. Use `self.client` for OpenAI/GPT-5 calls
3. Use structured output when possible: `response_format=ModelClass`
4. For images: Use `_generate_and_upload_image()` helper
5. For videos: Follow Sora polling pattern in `generate_character_audition_video()`
6. Add retry logic for reliability (3 attempts recommended)

### Background Job Pattern
```python
async def process_job(job_id: str, ...):
    try:
        job_manager.update_job_status(job_id, JobStatus.processing)
        # Get hash for conflict detection
        initial_hash = await storage.get_current_hash_from_id(drama_id)

        # Do work...

        # Save with hash verification
        await storage.save_drama(drama, expected_hash=initial_hash)
        job_manager.update_job_status(job_id, JobStatus.completed, result={...})
    except Exception as e:
        job_manager.update_job_status(job_id, JobStatus.failed, error=str(e))

@router.post("/endpoint")
async def endpoint(background_tasks: BackgroundTasks, ...):
    job_id = generate_id("job")
    job_manager.create_job(job_id, drama_id, JobType.some_type)
    background_tasks.add_task(process_job, job_id, ...)
    return JobResponse(jobId=job_id, status=JobStatus.pending, ...)
```

## Railway Deployment

```bash
# Deploy to Railway
railway login
railway init
# Set environment variables (see RAILWAY_DEPLOYMENT.md)
railway up

# View logs
railway logs

# Get deployment URL
railway domain
```

Configuration files:
- `Procfile`: Process definition (`web: uvicorn main:app --host 0.0.0.0 --port $PORT`)
- `railway.toml`: Build/deployment config
- `runtime.txt`: Python version (3.11.11)

## Known Limitations

1. **Job persistence**: Jobs stored in-memory, lost on restart → Add Redis/DB for production
2. **List dramas performance**: Inefficient for large datasets (fetches all JSONs) → Use database with metadata index
3. **Concurrent drama modifications**: Optimistic locking helps but retry logic may be needed in clients
4. **R2 credentials**: Must be configured manually for production
5. **Image/video generation failures**: Retry logic mitigates but failures still possible

## API Design Philosophy

- **Async-first**: Long-running operations (AI generation) return job ID immediately
- **Nested resources**: RESTful paths reflect entity relationships
- **Optimistic locking**: Hash-based conflict detection for critical operations
- **Structured output**: GPT-5 with Pydantic models ensures type safety
- **Graceful degradation**: Image/video generation failures logged but don't fail entire job
