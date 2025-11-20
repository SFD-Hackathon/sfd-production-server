# Supabase Integration Migration Guide

This document outlines the migration from R2-based storage to Supabase database for drama and job persistence.

## Overview

The backend has been updated to use Supabase as the primary data store, replacing the previous R2 JSON-based storage for dramas and file-based job storage.

### What Changed

**Before:**
- Dramas stored as JSON files in R2 (`dramas/{drama_id}/drama.json`)
- Jobs stored as JSON files in `./jobs/` directory
- All assets (images, videos) stored in R2

**After:**
- Dramas, characters, episodes, and scenes stored in Supabase database tables
- Jobs stored in Supabase database with hierarchical support
- R2 still used for binary assets (images, videos, audio)

## Architecture

### Data Access Layer (DAL)

New abstraction layer for database operations:

```
app/dal/
├── __init__.py           # Module exports
├── supabase_client.py    # Singleton Supabase client manager
├── base.py               # Base repository with common CRUD operations
├── job_repository.py     # Job operations with hierarchical DAG support
├── drama_repository.py   # Drama operations with nested data handling
└── user_repository.py    # User authentication and management
```

### Repository Pattern

All database operations now go through repositories instead of direct storage:

```python
# Old (R2 storage)
from app.storage import storage
drama = await storage.get_drama(drama_id)
await storage.save_drama(drama)

# New (Supabase repositories)
from app.dal import get_supabase_client, DramaRepository
repo = DramaRepository(get_supabase_client())
drama = await repo.get_drama_complete(drama_id)
await repo.save_drama_complete(drama, user_id="10000")
```

### Updated Components

1. **GraphQL Schema** (`app/graphql_schema.py`)
   - Queries use `DramaRepository` instead of `storage`
   - Mutations use `DramaRepository.save_drama_complete()`
   - User authentication placeholder added (TODO: implement proper auth)

2. **Hierarchical DAG Executor** (`app/hierarchical_dag_engine.py`)
   - Now async-first (uses `asyncio` instead of threading)
   - Uses `JobRepository` for job persistence
   - Supports hierarchical job tracking with parent/child relationships

3. **Configuration** (`app/config.py`, `main.py`)
   - Added Supabase environment variables
   - Supabase client initialized in FastAPI lifespan
   - Graceful fallback if Supabase unavailable

## Environment Variables

Add these to your `.env` file:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key-here
SUPABASE_ANON_KEY=your-anon-key-here
```

See `.env.example` for complete configuration template.

## Database Schema

The Supabase schema includes:

- `users` - User accounts with token management
- `dramas` - Drama metadata
- `characters` - Characters with references to dramas
- `episodes` - Episodes with references to dramas
- `scenes` - Scenes with references to episodes
- `jobs` - Job tracking with hierarchical DAG support

See `supabase/migrations/001_fresh_schema.sql` for full schema.

## Migration Steps

### For Fresh Start (Recommended)

If you're okay starting with a clean database:

1. Set up Supabase environment variables
2. Run database migration:
   ```bash
   supabase db reset
   ```
3. Start the server - it will automatically use Supabase
4. Create dramas using the API as usual

### For Migrating Existing Data

If you have existing dramas in R2 that need to be migrated:

1. **Create migration script** (not yet implemented):
   - Read dramas from R2
   - Transform to Supabase schema
   - Insert via `DramaRepository.save_drama_complete()`

2. **Example migration logic**:
   ```python
   from app.storage import storage  # Old R2 storage
   from app.dal import get_supabase_client, DramaRepository

   # Get all dramas from R2
   dramas, _ = await storage.list_dramas(limit=1000)

   # Insert into Supabase
   repo = DramaRepository(get_supabase_client())
   for drama in dramas:
       await repo.save_drama_complete(drama, user_id="10000")
   ```

3. **Migration considerations**:
   - User ID mapping (all existing dramas use default user "10000")
   - Binary assets remain in R2 (no migration needed)
   - Jobs are not migrated (historical jobs can be discarded)

## Feature Flags (Future)

For gradual migration, consider adding feature flags:

```python
USE_SUPABASE = os.getenv("USE_SUPABASE", "true") == "true"

if USE_SUPABASE:
    repo = DramaRepository(get_supabase_client())
    drama = await repo.get_drama_complete(drama_id)
else:
    drama = await storage.get_drama(drama_id)  # Fallback to R2
```

## Testing

1. **Verify Supabase connection**:
   ```bash
   python -c "from app.dal.supabase_client import check_supabase_connection; print(check_supabase_connection())"
   ```

2. **Test GraphQL endpoint**:
   ```bash
   curl -X POST http://localhost:8000/graphql \
     -H "Content-Type: application/json" \
     -d '{"query": "{ dramas { id title } }"}'
   ```

3. **Test drama creation**:
   ```bash
   curl -X POST http://localhost:8000/dramas \
     -H "Content-Type: application/json" \
     -d '{"premise": "Test drama", "model": "gemini-3-pro-preview"}'
   ```

## Rollback

If you need to rollback to R2 storage:

1. Checkout the previous branch
2. Remove Supabase environment variables
3. Restart the server

The old R2 storage code is preserved in `app/storage.py`.

## Known Limitations

1. **User Authentication**: Currently uses placeholder user_id "10000"
   - TODO: Implement proper JWT/API key authentication
   - TODO: Extract user_id from auth context in GraphQL and REST endpoints

2. **Job Types**: Job types mapped to backend enums (`generate_drama`, `generate_image`, `generate_video`)
   - Ensure consistency with Flutter client job type translator

3. **API Key Validation**: Placeholder implementation in `UserRepository.validate_api_key()`
   - TODO: Create proper `api_keys` table with hashed keys
   - TODO: Implement key rotation and rate limiting

## Next Steps

1. Implement proper user authentication
2. Update REST API endpoints to use repositories
3. Create actual migration script for existing data
4. Add real-time event publishing via Supabase Realtime
5. Optimize with connection pooling and caching
6. Update documentation and API specs

## Support

For issues or questions:
- Check Supabase logs: `supabase logs`
- Check application logs
- Verify environment variables are set correctly
- Ensure database migrations are applied: `supabase db reset`
