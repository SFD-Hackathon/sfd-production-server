# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI-based Drama Generation API with AI-powered asset generation (GPT-5 for scripts, Gemini for images, Sora for videos). Features hierarchical DAG execution for batch generation, file-based job persistence, and R2 storage backend. Deployed on Railway.

**Tech Stack**: Python 3.11+, FastAPI, OpenAI GPT-5, Gemini (images), Sora (videos), R2 (storage), Railway (hosting)

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
# Install test dependencies
pip install -r test-requirements.txt
pip install pytest pytest-asyncio

# Provider tests (isolated, no server needed - RECOMMENDED for debugging)
pytest tests/test_providers.py -v -s  # All provider tests
pytest tests/test_providers.py::TestGeminiProvider -v -s  # Gemini only
pytest tests/test_providers.py -v -s -m "not slow"  # Skip video tests

# Integration tests (requires server running in another terminal)
pytest tests/test_generation.py -v -s  # Full hierarchical DAG tests
python tests/test_api.py              # Basic API tests
python tests/test_drama_create.py     # Drama creation tests

# See tests/README.md for detailed test guide
```

**Testing Strategy:**
1. **Provider tests first** - If API calls fail, test providers in isolation
2. **Integration tests second** - Test full workflow with server running
3. **Use provider tests to debug** - Faster feedback loop, isolates issues

### Drama Viewer (Debugging UI)
```bash
# Run Streamlit viewer (requires API server running)
streamlit run viewer/app.py
# OR use quick start script
./run_viewer.sh

# Access viewer at http://localhost:8501
# See viewer/README.md for full documentation
```

### Code Quality
```bash
pip install black isort
black .
isort .
```

### Compile Check (IMPORTANT - Avoid Import Errors)
**ALWAYS run compile check before committing to catch missing imports and syntax errors:**

```bash
# Check specific file
python -m py_compile app/providers/gemini_provider.py

# Check specific module (includes import validation)
python -c "from app.providers.gemini_provider import GeminiProvider"

# Check all Python files in a directory
find app -name "*.py" -exec python -m py_compile {} \;

# Check if server can start (validates all imports)
python -c "from main import app; print('✓ All imports valid')"
```

**Common import errors to watch for:**
- Missing `import logging` when using `logger`
- Missing model imports when using type hints
- Circular imports between modules
- Missing third-party package imports

**Best practice:** Add compile check to pre-commit hook or run manually before git push.

## High-Level Architecture

### Three-Tier Generation System

**Tier 1: Drama Structure Generation (GPT-5)**
- Client sends premise → `POST /dramas`
- GPT-5 generates drama structure (characters, episodes, scenes)
- Returns `202 Accepted` with `jobId` for polling
- Duration: 30-60 seconds

**Tier 2: Asset Generation DAG (Hierarchical)**
- Client triggers DAG → `POST /dramas/{id}/generate`
- Hierarchical DAG executor orchestrates parallel asset generation
- Returns `jobId` for progress tracking
- Duration: 5-15 minutes for full drama

**Tier 3: Individual Asset Generation**
- Client can generate single assets: `POST /dramas/{id}/characters/{id}/generate`
- Direct Gemini/Sora API calls
- Immediate or async depending on asset type

### Hierarchical DAG Architecture

```
Drama (Root)
├── h=1: Characters (parallel)
│   ├── Character Portrait (Gemini image)
│   └── h=2: Character Assets (depends on character)
│       └── Audition Video (Sora video)
└── h=1: Episodes (parallel)
    └── h=2: Scenes (depends on episode, parallel within episode)
        ├── Storyboard (Gemini image)
        └── h=3: Scene Assets (depends on scene)
            └── Video Clip (Sora video, depends on storyboard)
```

**Key Properties:**
- Nodes at same hierarchy level execute in parallel
- Child nodes wait for parent completion
- Cross-references supported (e.g., scene references character)
- Automatic dependency resolution from drama structure

### Core Components

**app/config.py**: Centralized configuration module (not Pydantic Settings)
- Loads `.env` in development, uses environment variables in production
- Validates critical configuration on startup
- Prints configuration summary for debugging
- Single source of truth for all env vars

**app/hierarchical_dag_engine.py**: Hierarchical DAG executor
- `HierarchicalDAGExecutor`: Builds and executes drama generation DAG
- `DAGNode`: Represents entity in generation graph
- Automatic dependency extraction from Drama model structure
- Parallel execution within hierarchy levels
- Parent/child job tracking for progress monitoring
- Integrates with AssetLibrary for R2 uploads

**app/job_storage.py**: File-based job persistence
- Replaces in-memory job manager
- Thread-safe JSON file operations with fcntl locking
- Jobs stored in `./jobs/` directory (configurable via `JOBS_DIR`)
- Parent/child job hierarchy support
- Survives server restarts

**app/asset_library.py**: R2 storage abstraction with metadata
- User/project-based organization: `{user_id}/{project_name}/assets/`
- Metadata management for all assets
- Tag-based classification (character, storyboard, clip)
- Type validation (image, video, text)
- Upload, download, list, delete operations

**app/image_generation.py**: Gemini API integration
- `generate_image()`: Character portraits and storyboards
- 9:16 aspect ratio enforced via reference image
- Retry logic (3 attempts)
- Local output caching in `./outputs/`

**app/video_generation.py**: Sora API integration
- `generate_video_sora()`: Character auditions and scene clips
- Polling-based job completion (max 10 min timeout)
- Duration control (default 10s)
- Retry logic (3 attempts)

**app/storage.py**: R2 drama persistence (same as before)
- Drama storage: `dramas/{drama_id}/drama.json`
- Optimistic locking with SHA256 hashing
- Conflict detection for concurrent modifications

**app/ai_service.py**: GPT-5 drama generation (same as before)
- `generate_drama()`: Text premise → Drama structure
- `improve_drama()`: Feedback-based regeneration
- `critique_drama()`: Quality assessment
- Structured output with DramaLite → Drama conversion

### API Endpoints

**Drama Management:**
- `POST /dramas` - Create from premise (async) or JSON (sync)
- `GET /dramas` - List with pagination
- `GET /dramas/{id}` - Get single drama
- `PATCH /dramas/{id}` - Update drama
- `DELETE /dramas/{id}` - Delete drama + assets
- `POST /dramas/{id}/improve` - Improve with feedback (async)
- `POST /dramas/{id}/critique` - Get AI critique (async)

**Generation Endpoints (NEW):**
- `POST /dramas/{id}/generate` - Execute full drama DAG (all assets)
- `POST /dramas/{id}/episodes/{episode_id}/generate` - Episode-level DAG
- `POST /dramas/{id}/characters/{character_id}/generate` - Single character portrait
- `POST /dramas/{id}/episodes/{episode_id}/scenes/{scene_id}/generate` - Scene generation

**Asset Library (NEW):**
- `GET /asset-library/list` - List assets with filters
- `POST /asset-library/upload` - Direct asset upload
- `GET /asset-library/{asset_id}` - Download asset
- `DELETE /asset-library/{asset_id}` - Delete asset
- `GET /asset-library/{asset_id}/metadata` - Get metadata only

**Job Tracking:**
- `GET /dramas/{dramaId}/jobs/{jobId}` - Get job status (supports parent/child hierarchy)
- `GET /dramas/{dramaId}/jobs` - List all jobs for drama

**Nested Resources:**
- Characters: `GET/PATCH /dramas/{id}/characters/{id}`
- Episodes: `GET/PATCH /dramas/{id}/episodes/{id}`
- Scenes: `GET/PATCH /dramas/{id}/episodes/{id}/scenes/{id}`
- Assets: `GET/PATCH /dramas/{id}/episodes/{id}/scenes/{id}/assets/{id}`

## Environment Variables

**Critical (required for full functionality):**
- `OPENAI_API_KEY` - GPT-5 drama structure generation
- `GEMINI_API_KEY` - Image generation (character portraits, storyboards)
- `SORA_API_KEY` - Video generation (auditions, clips)
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` - R2 storage
- `R2_BUCKET` - R2 bucket name (default: sfd-production)
- `R2_PUBLIC_URL` - Public URL for R2 assets

**Optional:**
- `API_KEYS` - Comma-separated API keys (empty = no auth)
- `GPT_MODEL` - GPT model (default: gpt-5)
- `GEMINI_API_BASE` - Gemini endpoint (default: googleapis)
- `SORA_API_BASE` - Sora endpoint (default: t8star)
- `ENVIRONMENT` - development/production
- `PORT` - Server port (default: 8000)
- `JOBS_DIR` - Job storage directory (default: ./jobs)
- `OUTPUTS_DIR` - Local output cache (default: ./outputs)
- `DEFAULT_ASPECT_RATIO` - Video aspect ratio (default: 9:16)
- `DEFAULT_VIDEO_DURATION` - Video duration in seconds (default: 10)
- `MAX_RETRIES` - Retry attempts for failed generations (default: 2)

## Key Implementation Details

### Hierarchical DAG Execution Flow

1. **DAG Building** (`build_hierarchical_dag()`):
   - Extracts entities from Drama model
   - Creates DAGNode for each entity
   - Resolves dependencies automatically:
     - Parent-child relationships (scene → episode)
     - Cross-references (scene asset → character)
   - Assigns hierarchy levels (h=1, h=2, h=3)

2. **DAG Execution** (`execute_dag()`):
   - Groups nodes by hierarchy level
   - Executes each level sequentially
   - Within each level, nodes execute in parallel (asyncio)
   - Creates child job for each node
   - Updates parent job progress
   - Uploads all assets to AssetLibrary

3. **Job Hierarchy**:
   - Parent job: Overall DAG execution
   - Child jobs: Individual asset generation
   - Status aggregation: parent shows total/completed/failed/running counts

### File-Based Job Persistence

**Storage Pattern:**
```
./jobs/
├── job_abc123.json
├── job_def456.json
└── job_parent_xyz.json
```

**Thread Safety:**
- Read operations: Shared lock (fcntl.LOCK_SH)
- Write operations: Exclusive lock (fcntl.LOCK_EX)
- Automatic lock release on file close

**Job Data Structure:**
```json
{
  "job_id": "job_abc123",
  "drama_id": "drama_xyz",
  "asset_id": "char_001",
  "job_type": "image",
  "status": "completed",
  "prompt": "Character description...",
  "r2_url": "https://...",
  "created_at": "2025-01-19T...",
  "completed_at": "2025-01-19T...",
  "parent_job_id": "job_parent_xyz",
  "metadata": {...}
}
```

### Asset Library Organization

**R2 Structure:**
```
{user_id}/
└── {project_name}/
    └── assets/
        ├── {asset_id}.png (character portrait)
        ├── {asset_id}.mp4 (video clip)
        └── {asset_id}_metadata.json
```

**Metadata Schema:**
```json
{
  "asset_id": "uuid",
  "user_id": "10000",
  "project_name": "drama_xyz",
  "asset_type": "image",
  "tag": "character",
  "filename": "char_001.png",
  "r2_key": "10000/drama_xyz/assets/...",
  "public_url": "https://...",
  "size_bytes": 123456,
  "created_at": "2025-01-19T...",
  "metadata": {
    "job_id": "job_abc123",
    "prompt": "...",
    "source": "ai_generation"
  }
}
```

### Generation Retry Logic

Both image and video generation include retry logic:
- **Total attempts**: 3 (initial + 2 retries)
- **Delay between retries**: 2-3 seconds
- **Failure handling**: Error logged, job marked as failed
- **Partial failures**: Other assets continue generating

### Optimistic Locking (Drama Persistence)

**Pattern** (unchanged from before):
1. Get hash before modification: `initial_hash = await storage.get_current_hash_from_id(drama_id)`
2. Perform operations (AI generation, image creation)
3. Save with verification: `await storage.save_drama(drama, expected_hash=initial_hash)`
4. Raises `StorageConflictError` if concurrent modification detected

**When to use:**
- Full drama generation job (protects entire workflow)
- Drama improvement job
- Critical updates that must not be lost

## Common Development Patterns

### Adding a New Generation Endpoint

```python
@router.post("/{drama_id}/entity/{entity_id}/generate")
async def generate_entity(drama_id: str, entity_id: str, background_tasks: BackgroundTasks):
    # 1. Validate drama exists
    drama = await storage.get_drama(drama_id)
    if not drama:
        raise HTTPException(404, "Drama not found")

    # 2. Create job
    from app.job_storage import get_storage
    job_storage = get_storage()
    job = job_storage.create_job(
        drama_id=drama_id,
        asset_id=entity_id,
        job_type="image",  # or "video"
        prompt="..."
    )

    # 3. Queue background task
    background_tasks.add_task(process_generation, job["job_id"], drama_id, entity_id)

    # 4. Return job response
    return JobResponse(
        jobId=job["job_id"],
        dramaId=drama_id,
        status="pending",
        message=f"Poll GET /dramas/{drama_id}/jobs/{job['job_id']} for status"
    )

async def process_generation(job_id: str, drama_id: str, entity_id: str):
    job_storage = get_storage()
    try:
        job_storage.update_job(job_id, {"status": "running"})

        # Generate asset
        from app.image_generation import generate_image
        result = generate_image(prompt="...", job_id=job_id)

        # Upload to R2
        from app.asset_library import AssetLibrary
        lib = AssetLibrary(user_id="10000", project_name=drama_id)
        with open(result["local_path"], "rb") as f:
            asset = lib.upload_asset(
                content=f.read(),
                asset_type="image",
                tag="character",
                filename=f"{entity_id}.png",
                metadata={"job_id": job_id}
            )

        job_storage.update_job(job_id, {
            "status": "completed",
            "r2_url": asset["public_url"]
        })
    except Exception as e:
        job_storage.update_job(job_id, {"status": "failed", "error": str(e)})
```

### Using Hierarchical DAG Executor

```python
from app.hierarchical_dag_engine import HierarchicalDAGExecutor

# Full drama generation
executor = HierarchicalDAGExecutor(
    drama=drama_model,
    user_id="10000",
    project_name=drama_model.id
)
result = executor.execute_dag()

# Episode-only generation (filter by episode_id)
# Modify executor to filter nodes before execution
filtered_nodes = {
    node_id: node
    for node_id, node in executor.nodes.items()
    if node.metadata.get("episode_id") == target_episode_id
}
```

### Accessing Job Storage

```python
from app.job_storage import get_storage

job_storage = get_storage()

# Create job
job = job_storage.create_job(
    drama_id="drama_123",
    asset_id="char_001",
    job_type="image",
    prompt="Character portrait",
    parent_job_id="job_parent_xyz"  # Optional for child jobs
)

# Get job
job = job_storage.get_job("job_abc123")

# Update job
job_storage.update_job("job_abc123", {
    "status": "completed",
    "r2_url": "https://..."
})

# List jobs
jobs = job_storage.list_jobs(drama_id="drama_123", status="completed")
```

### Using Asset Library

```python
from app.asset_library import AssetLibrary

# Initialize for project
lib = AssetLibrary(user_id="10000", project_name="drama_xyz")

# Upload asset
with open("character.png", "rb") as f:
    asset = lib.upload_asset(
        content=f.read(),
        asset_type="image",
        tag="character",
        filename="char_001.png",
        metadata={"prompt": "Detective character", "job_id": "job_123"}
    )
# Returns: {"asset_id": "...", "public_url": "...", "r2_key": "..."}

# List assets
assets = lib.list_assets(asset_type="image", tag="character")

# Get asset
content, metadata = lib.get_asset(asset_id="...", asset_type="image")

# Delete asset
lib.delete_asset(asset_id="...", asset_type="image")
```

## Testing Guide

See `TESTING.md` for comprehensive testing documentation.

**Quick Start:**
```bash
# Terminal 1: Start server
python main.py

# Terminal 2: Run tests
pytest tests/test_generation.py -v -s  # Hierarchical DAG tests
python tests/test_drama_create.py      # Drama creation tests
```

**Test Levels:**
- Asset-level: Single character/scene generation (~30-60s)
- Episode-level: Full episode DAG (~2-5 min)
- Drama-level: Full drama DAG (~5-15 min)

## Railway Deployment

```bash
# Deploy to Railway
railway login
railway init

# Set environment variables (critical)
railway variables set OPENAI_API_KEY=...
railway variables set GEMINI_API_KEY=...
railway variables set SORA_API_KEY=...
railway variables set R2_ACCOUNT_ID=...
railway variables set R2_ACCESS_KEY_ID=...
railway variables set R2_SECRET_ACCESS_KEY=...
railway variables set R2_BUCKET=sfd-production
railway variables set R2_PUBLIC_URL=https://pub-xxx.r2.dev
railway variables set ENVIRONMENT=production
railway variables set API_KEYS=prod-key-1,prod-key-2

# Deploy
railway up

# View logs
railway logs

# Get URL
railway domain
```

**Configuration files:**
- `Procfile`: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- `railway.toml`: Build/deployment config
- `requirements.txt`: Dependencies (includes gunicorn)

## Migration Status

See `MIGRATION_STATUS.md` for detailed migration notes from ai-short-drama-web-app backend.

**Current Status:** Core modules integrated, hierarchical DAG operational, testing infrastructure complete.

## Known Limitations & Considerations

1. **Job persistence**: File-based, not ideal for high-scale production
   - Consider PostgreSQL + parent_job_id foreign key for production
   - Current solution works well for <1000 concurrent jobs

2. **Drama listing performance**: Fetches all JSONs (unchanged limitation)
   - Use database with metadata index for production scale

3. **DAG execution**: Single-server, not distributed
   - For massive parallelism, consider Celery/RQ with Redis
   - Current solution handles ~50 assets in parallel efficiently

4. **R2 rate limits**: No built-in rate limiting
   - Monitor R2 API quotas
   - Add rate limiting middleware if needed

5. **Local file caching**: `./outputs/` directory grows over time
   - Implement cleanup policy or use tmpfs
   - Files stored only for debugging/retry

6. **No resume functionality**: DAG execution cannot resume from checkpoint
   - Add checkpoint persistence for long-running DAGs
   - Currently must restart entire DAG on failure

## Architecture Evolution Notes

**Original Design (v1.0):**
- In-memory job manager
- Direct Gemini/Sora calls in routers
- No batch generation support
- Limited parallelism

**Current Design (v2.0):**
- File-based job persistence (survives restarts)
- Hierarchical DAG executor (efficient batch generation)
- Asset library abstraction (metadata management)
- Parallel execution within hierarchy levels
- Modular generation services (image_generation.py, video_generation.py)
- Comprehensive testing infrastructure

**Key Design Principles:**
- Async-first: Long operations return job ID immediately
- Hierarchical parallelism: Maximize throughput within constraints
- Conflict detection: Optimistic locking prevents lost updates
- Graceful degradation: Asset failures don't fail entire job
- Persistence: Jobs survive server restarts
- Modularity: Clear separation of concerns (DAG, storage, generation)
