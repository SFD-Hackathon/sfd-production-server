# Hierarchical DAG Engine Implementation

## Summary

Improved the DAG execution engine to support hierarchical drama generation architecture.

## Hierarchical Architecture

```
Root: Drama
├── h=1: Characters (parallel)
│   └── h=2: Character Assets (depends on parent character)
└── h=1: Episodes (parallel)
    └── h=2: Scenes (depends on parent episode)
        └── h=3: Scene Assets (depends on parent scene + optional character refs)
```

## Implementation

### New File: `app/hierarchical_dag_engine.py`

**Key Features:**
1. **DAGNode class** - Represents nodes at different hierarchy levels
2. **Automatic dependency resolution** - Builds dependencies from drama structure:
   - Characters & Episodes: Level 1, no dependencies
   - Character Assets: Level 2, depend on parent character
   - Scenes: Level 2, depend on parent episode
   - Scene Assets: Level 3, depend on parent scene + character references

3. **Parallel execution within levels** - All nodes at the same level execute in parallel
4. **Supports all asset types**: images (characters, storyboards) and videos (clips)
5. **R2 upload integration** - All generated assets uploaded to AssetLibrary

### Updated Endpoints

#### `/dramas/{drama_id}/generate`
- **Returns**: `JobResponse` with `job_id` and `status`
- **Behavior**: Executes full drama DAG (all characters, episodes, scenes, assets)
- **Response**:
```json
{
  "dramaId": "drama_xyz",
  "jobId": "job_abc123",
  "status": "pending",
  "message": "Drama asset generation DAG queued..."
}
```

#### `/dramas/{drama_id}/episodes/{episode_id}/generate`
- **Returns**: `JobResponse` with `job_id` and `status`
- **Behavior**: Executes DAG for single episode (scenes + scene assets only)
- **Response**:
```json
{
  "dramaId": "drama_xyz",
  "jobId": "job_def456",
  "status": "pending",
  "message": "Episode asset generation queued..."
}
```

## Execution Flow

### Full Drama Generation (`POST /dramas/{id}/generate`)

1. **Level 0**: Characters & Episodes execute in parallel
   - Generate character portraits
   - Episodes are placeholders (no assets)

2. **Level 1**: Character Assets & Scenes execute in parallel
   - Character assets depend on their parent characters
   - Scenes (storyboards) depend on their parent episodes
   - Can reference characters via `depends_on`

3. **Level 2**: Scene Assets execute in parallel
   - Video clips depend on their parent scenes
   - Can reference scene storyboard or character images

### Episode Generation (`POST /dramas/{id}/episodes/{episode_id}/generate`)

Filters DAG to only process nodes related to specified episode:
1. **Level 0**: Scenes for this episode
2. **Level 1**: Scene assets for these scenes

## Example DAG Structure

```
drama_123
├─ char_c001 (Level 1)
│  ├─ char_asset_c001_a001 (Level 2, depends on char_c001)
│  └─ char_asset_c001_a002 (Level 2, depends on char_c001)
├─ char_c002 (Level 1)
│  └─ char_asset_c002_a001 (Level 2, depends on char_c002)
├─ ep_e001 (Level 1)
│  ├─ scene_e001_s001 (Level 2, depends on ep_e001)
│  │  ├─ scene_asset_e001_s001_a001 (Level 3, depends on scene_e001_s001)
│  │  └─ scene_asset_e001_s001_a002 (Level 3, depends on scene_e001_s001, char_c001)
│  └─ scene_e001_s002 (Level 2, depends on ep_e001)
│     └─ scene_asset_e001_s002_a001 (Level 3, depends on scene_e001_s002)
└─ ep_e002 (Level 1)
   └─ scene_e002_s001 (Level 2, depends on ep_e002)
      └─ scene_asset_e002_s001_a001 (Level 3, depends on scene_e002_s001, char_c002)
```

## Dependency Resolution

The engine automatically extracts dependencies from the Drama model:

1. **Parent-Child** (implicit):
   - Character assets → parent character
   - Scenes → parent episode
   - Scene assets → parent scene

2. **Cross-References** (explicit via `Asset.depends_on`):
   - Scene assets can reference characters (for character consistency)
   - Scene assets can reference other scene assets (e.g., video depends on storyboard)

## Job Management

Each node in the DAG creates a child job:
- **Parent Job**: Tracks overall DAG execution
- **Child Jobs**: One per node, tracks individual asset generation

Job polling returns:
```json
{
  "job_id": "job_abc",
  "status": "running",
  "total_jobs": 15,
  "completed_jobs": 8,
  "failed_jobs": 0,
  "running_jobs": 3,
  "pending_jobs": 4,
  "jobs": [...]
}
```

## Benefits

1. **Parallel Execution**: All nodes at same level execute simultaneously
2. **Automatic Dependency Management**: No manual dependency tracking needed
3. **Hierarchical Organization**: Respects drama structure (drama → episode → scene)
4. **Flexible**: Easy to filter for partial generation (single episode, single character)
5. **R2 Integration**: All assets uploaded with proper metadata
6. **Resumable**: Can resume failed DAG executions

## Usage

```python
from app.hierarchical_dag_engine import HierarchicalDAGExecutor

# Full drama generation
executor = HierarchicalDAGExecutor(
    drama=drama_model,
    user_id="10000",
    project_name="my_drama"
)
result = executor.execute_dag()

# Resume after failure
result = executor.execute_dag(resume=True)
```

## API Consistency

All generation endpoints now return consistent response:
```json
{
  "dramaId": "...",
  "jobId": "...",
  "status": "pending",
  "message": "..."
}
```

This matches the pattern used by:
- `POST /dramas` (create from premise)
- `POST /dramas/{id}/improve`
- `POST /dramas/{id}/critic`
- `POST /dramas/{id}/characters/{id}/audition`
