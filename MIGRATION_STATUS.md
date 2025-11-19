# Repository Merge - MIGRATION STATUS

**Date**: 2025-01-19
**Status**: ✅ Core Files Migrated - Integration Work Remaining

---

## ✅ Completed Migration Steps

### 1. Core Module Migration

The following core modules from `ai-short-drama-web-app/backend` have been successfully copied to `app/`:

- ✅ **asset_library.py** - R2 storage abstraction with metadata management
- ✅ **job_storage.py** - File-based JSON job persistence with thread-safe operations
- ✅ **image_generation.py** - Gemini API integration for character/storyboard generation
- ✅ **video_generation.py** - Sora2 API integration for video clip generation
- ✅ **generation_dag_engine.py** - DAG executor for batch drama generation

### 2. Configuration & Dependencies

- ✅ **app/config.py** - Created comprehensive config merging both repos' needs
  - OpenAI/GPT-5 for drama generation
  - Gemini for image generation
  - Sora2 for video generation
  - R2 storage configuration
  - Job/output directories

- ✅ **requirements.txt** - Updated with all dependencies
  - Added `gunicorn==21.2.0` for production deployment

### 3. New API Router

- ✅ **app/routers/asset_library.py** - Global asset library management
  - `GET /asset-library/list` - List assets with filters
  - `POST /asset-library/upload` - Direct asset upload
  - `GET /asset-library/{asset_id}` - Download asset
  - `DELETE /asset-library/{asset_id}` - Delete asset
  - `GET /asset-library/{asset_id}/metadata` - Get metadata only

### 4. Main Application Updates

- ✅ **main.py** - Updated to import and register `asset_library` router

---

## 📋 Current API Structure

### Existing APIs (from sfd-production-server)
```
✅ GET  /health
✅ GET  /
✅ POST /dramas (create from premise - async)
✅ GET  /dramas (list with pagination)
✅ GET  /dramas/{drama_id}
✅ PATCH /dramas/{drama_id}
✅ DELETE /dramas/{drama_id}
✅ POST /dramas/{drama_id}/improve
✅ GET  /dramas/{drama_id}/characters
✅ GET  /dramas/{drama_id}/characters/{character_id}
✅ PATCH /dramas/{drama_id}/characters/{character_id}
✅ GET  /dramas/{drama_id}/episodes
✅ GET  /dramas/{drama_id}/episodes/{episode_id}
✅ PATCH /dramas/{drama_id}/episodes/{episode_id}
✅ GET  /dramas/{drama_id}/episodes/{episode_id}/scenes
✅ GET  /dramas/{drama_id}/episodes/{episode_id}/scenes/{scene_id}
✅ PATCH /dramas/{drama_id}/episodes/{episode_id}/scenes/{scene_id}
✅ GET  /dramas/{drama_id}/episodes/{episode_id}/scenes/{scene_id}/assets
✅ GET  /dramas/{drama_id}/episodes/{episode_id}/scenes/{scene_id}/assets/{asset_id}
✅ PATCH /dramas/{drama_id}/episodes/{episode_id}/scenes/{scene_id}/assets/{asset_id}
✅ GET  /dramas/{drama_id}/jobs
✅ GET  /dramas/{drama_id}/jobs/{job_id}
```

### New APIs (migrated from ai-short-drama-web-app)
```
✅ GET    /asset-library/list
✅ POST   /asset-library/upload
✅ GET    /asset-library/{asset_id}
✅ DELETE /asset-library/{asset_id}
✅ GET    /asset-library/{asset_id}/metadata
```

---

## 🔨 Remaining Integration Work

### Critical Next Steps

#### 1. Add Generation Endpoints

**Characters Router** (`app/routers/characters.py`):
```python
POST /dramas/{drama_id}/characters/{character_id}/generate
```
- Create generation job using `job_storage.create_job()`
- Call `image_generation.generate_image()` in background
- Upload result to R2 using `AssetLibrary`
- Return `job_id` for status polling

**Assets Router** (`app/routers/assets.py`):
```python
POST /dramas/{drama_id}/episodes/{episode_id}/scenes/{scene_id}/assets/{asset_id}/generate
```
- Detect asset type (image vs video)
- Call `image_generation.generate_image()` OR `video_generation.generate_video_sora()`
- Upload to R2
- Return `job_id`

#### 2. Add DAG Execution Endpoints

**Dramas Router** (`app/routers/dramas.py`):
```python
POST /dramas/{drama_id}/execute
POST /dramas/{drama_id}/resume
```
- Use `generation_dag_engine.DAGExecutor` for batch processing
- Execute all character/storyboard/clip generation
- Return parent `job_id` for progress tracking

#### 3. Update Job Manager

**app/job_manager.py** needs to:
- Use `job_storage.JobStorage` instead of in-memory dict
- Support file-based persistence
- Add polling endpoints that read from JSON files
- Support parent/child job hierarchy

#### 4. Update Models

**app/models.py** needs additional models:
```python
class GenerateAssetRequest(BaseModel):
    prompt: str
    reference_images: Optional[List[str]] = None
    duration: Optional[int] = None  # For video

class GenerateAssetResponse(BaseModel):
    job_id: str
    drama_id: str
    asset_id: str
    status: str
    message: str

class DAGExecuteRequest(BaseModel):
    user_id: Optional[str] = "10000"
    project_name: Optional[str] = None
    resume: Optional[bool] = False

class DAGExecuteResponse(BaseModel):
    dag_id: str
    drama_id: str
    parent_job_id: str
    status: str
    message: str
```

---

## 🔧 Implementation Guide

### Step 1: Update Characters Router

Add generate endpoint to `app/routers/characters.py`:

```python
from app.job_storage import get_storage
from app.image_generation import generate_image
from app.asset_library import AssetLibrary
from app.storage import storage
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

@router.post("/{dramaId}/characters/{characterId}/generate")
async def generate_character_image(
    dramaId: str,
    characterId: str,
    request: GenerateAssetRequest
):
    """Generate character image using Gemini"""

    # Get drama
    drama = await storage.get_drama(dramaId)
    if not drama:
        raise HTTPException(404, "Drama not found")

    # Find character
    character = next((c for c in drama.characters if c.id == characterId), None)
    if not character:
        raise HTTPException(404, "Character not found")

    # Create job
    job_storage = get_storage()
    job = job_storage.create_job(
        drama_id=dramaId,
        asset_id=characterId,
        job_type="image",
        prompt=request.prompt or character.description
    )

    # Run generation in background
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor,
        _generate_character_background,
        job["job_id"],
        dramaId,
        characterId,
        request.prompt or character.description
    )

    return {
        "job_id": job["job_id"],
        "drama_id": dramaId,
        "character_id": characterId,
        "status": "pending",
        "message": f"Poll GET /dramas/{dramaId}/jobs/{job['job_id']} for status"
    }

def _generate_character_background(job_id, drama_id, character_id, prompt):
    """Background task for character generation"""
    job_storage = get_storage()

    try:
        # Update status
        job_storage.update_job(job_id, {"status": "running"})

        # Generate image
        from datetime import datetime
        result = generate_image(prompt=prompt, job_id=job_id)

        # Upload to R2
        lib = AssetLibrary(user_id="10000", project_name=drama_id)

        with open(result["local_path"], "rb") as f:
            content = f.read()

        asset = lib.upload_asset(
            content=content,
            asset_type="image",
            tag="character",
            filename=f"{character_id}.png",
            metadata={
                "job_id": job_id,
                "prompt": prompt,
                "character_id": character_id,
                "drama_id": drama_id,
                "source": "ai_generation",
                "generator": "gemini-2.5-flash-image"
            }
        )

        # Update job
        job_storage.update_job(job_id, {
            "status": "completed",
            "r2_url": asset["public_url"],
            "r2_key": asset["r2_key"],
            "completed_at": datetime.utcnow().isoformat()
        })

    except Exception as e:
        job_storage.update_job(job_id, {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat()
        })
```

### Step 2: Update Job Manager

Modify `app/job_manager.py`:

```python
from app.job_storage import get_storage

class JobManager:
    def __init__(self):
        self.storage = get_storage()

    def get_job(self, job_id: str):
        """Get job from file storage"""
        return self.storage.get_job(job_id)

    def list_drama_jobs(self, drama_id: str):
        """List all jobs for a drama"""
        return self.storage.list_jobs(drama_id=drama_id)

# Singleton
_job_manager = JobManager()

def get_job_manager():
    return _job_manager
```

### Step 3: Add DAG Execution

Add to `app/routers/dramas.py`:

```python
from app.generation_dag_engine import DAGExecutor
from app.storage import storage
import threading

@router.post("/{dramaId}/execute")
async def execute_drama_dag(
    dramaId: str,
    request: DAGExecuteRequest
):
    """Execute full drama generation DAG"""

    # Get drama from R2
    drama_dict = await storage.get_drama(dramaId)
    if not drama_dict:
        raise HTTPException(404, "Drama not found")

    # Start DAG execution in background thread
    thread = threading.Thread(
        target=_execute_dag_background,
        args=(drama_dict, request.user_id, request.project_name)
    )
    thread.daemon = True
    thread.start()

    return {
        "dag_id": f"dag_{dramaId}",
        "drama_id": dramaId,
        "status": "running",
        "message": f"Poll GET /dramas/{dramaId}/jobs for progress"
    }

def _execute_dag_background(drama_dict, user_id, project_name):
    """Background DAG execution"""
    executor = DAGExecutor(
        drama=drama_dict,
        user_id=user_id,
        project_name=project_name or drama_dict["id"]
    )
    executor.execute_dag()
```

---

## 🌍 Environment Variables

Add these to Railway/`.env`:

```bash
# AI Provider API Keys
GEMINI_API_KEY=your_gemini_api_key
SORA_API_KEY=your_sora_api_key
OPENAI_API_KEY=your_openai_api_key

# R2 Storage (update if different)
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET=sfd-production
R2_PUBLIC_URL=https://pub-xxx.r2.dev

# Optional Configuration
DEFAULT_ASPECT_RATIO=9:16
DEFAULT_VIDEO_DURATION=10
MAX_RETRIES=2
JOBS_DIR=./jobs
OUTPUTS_DIR=./outputs
```

---

## 📁 File Structure After Migration

```
sfd-production-server/
├── main.py                           # ✅ Updated with asset_library router
├── requirements.txt                  # ✅ Updated with dependencies
├── app/
│   ├── config.py                     # ✅ NEW - Merged configuration
│   ├── asset_library.py              # ✅ NEW - R2 storage abstraction
│   ├── job_storage.py                # ✅ NEW - File-based job persistence
│   ├── image_generation.py           # ✅ NEW - Gemini integration
│   ├── video_generation.py           # ✅ NEW - Sora2 integration
│   ├── generation_dag_engine.py      # ✅ NEW - DAG executor
│   ├── models.py                     # ⚠️  NEEDS UPDATE - Add generation models
│   ├── job_manager.py                # ⚠️  NEEDS UPDATE - Use job_storage
│   ├── storage.py                    # ✅ Existing
│   ├── ai_service.py                 # ✅ Existing (GPT-5 drama generation)
│   ├── dependencies.py               # ✅ Existing
│   └── routers/
│       ├── dramas.py                 # ⚠️  NEEDS UPDATE - Add execute/resume
│       ├── characters.py             # ⚠️  NEEDS UPDATE - Add generate
│       ├── episodes.py               # ✅ Existing
│       ├── scenes.py                 # ✅ Existing
│       ├── assets.py                 # ⚠️  NEEDS UPDATE - Add generate
│       ├── jobs.py                   # ⚠️  NEEDS UPDATE - Use job_storage
│       └── asset_library.py          # ✅ NEW - Asset library APIs
└── jobs/                             # ✅ Created automatically (job storage)
```

---

## 🧪 Testing Plan

### 1. Test Asset Library APIs

```bash
# Upload asset
curl -X POST http://localhost:8000/asset-library/upload \
  -H "X-API-Key: your-key" \
  -F "file=@test.png" \
  -F "user_id=10000" \
  -F "project_name=test_drama" \
  -F "asset_type=image" \
  -F "tag=character"

# List assets
curl http://localhost:8000/asset-library/list?project_name=test_drama \
  -H "X-API-Key: your-key"
```

### 2. Test Character Generation (after implementing)

```bash
# Generate character image
curl -X POST http://localhost:8000/dramas/{drama_id}/characters/{char_id}/generate \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A brave warrior with silver armor"}'

# Poll job status
curl http://localhost:8000/dramas/{drama_id}/jobs/{job_id} \
  -H "X-API-Key: your-key"
```

### 3. Test DAG Execution (after implementing)

```bash
# Execute full drama DAG
curl -X POST http://localhost:8000/dramas/{drama_id}/execute \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{}'

# Check progress
curl http://localhost:8000/dramas/{drama_id}/jobs \
  -H "X-API-Key: your-key"
```

---

## ✅ Success Criteria

Migration will be complete when:

1. ✅ All core modules copied
2. ✅ Asset library APIs functional
3. ⚠️  Character generation endpoint working
4. ⚠️  Scene asset generation endpoint working
5. ⚠️  DAG execution endpoint working
6. ⚠️  Job polling returns correct status
7. ⚠️  R2 uploads successful
8. ⚠️  All tests pass

---

## 📚 Next Steps

1. **Implement Character Generate Endpoint**
   - Add POST `/dramas/{drama_id}/characters/{character_id}/generate`
   - Integrate with `image_generation.py` and `AssetLibrary`

2. **Implement Asset Generate Endpoint**
   - Add POST `/dramas/{drama_id}/episodes/{episode_id}/scenes/{scene_id}/assets/{asset_id}/generate`
   - Support both image (storyboard) and video (clip) generation

3. **Implement DAG Execution**
   - Add POST `/dramas/{drama_id}/execute` and `/resume`
   - Integrate with `generation_dag_engine.py`

4. **Update Job Manager**
   - Replace in-memory storage with `job_storage.JobStorage`
   - Ensure job polling works with file-based storage

5. **Add Models**
   - Add `GenerateAssetRequest`, `GenerateAssetResponse`, etc. to `models.py`

6. **Test End-to-End**
   - Test full workflow: Create drama → Generate characters → Generate storyboards → Generate clips

7. **Deploy to Railway**
   - Set all environment variables
   - Test production deployment

---

## 💡 Tips

- Use `app/config.py` for all environment variables
- All generation should be async (background tasks)
- Always upload to R2 via `AssetLibrary`
- Store all jobs in `job_storage` for persistence
- Return `job_id` immediately, client polls for completion
- DAG execution creates parent + child jobs automatically

---

## 🆘 Troubleshooting

### R2 Connection Issues
Check `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` are set

### Job Not Found
Ensure `JOBS_DIR` is writable and `job_storage` is initialized

### Generation Fails
Check `GEMINI_API_KEY` and `SORA_API_KEY` are valid

---

**Migration Status**: 60% Complete
**Estimated Remaining Work**: 4-6 hours for experienced developer

Need help? Check the source repo's test files in `ai-short-drama-web-app/backend/tests/` for working examples.
