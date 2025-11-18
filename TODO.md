# TODO: Database Migration

## Overview

Consider migrating from R2 object storage to a database-backed solution for drama persistence.

## Current Architecture: R2 Object Storage

### Pros
- **Simple**: Direct JSON serialization to S3-compatible storage
- **Serverless**: No database server to manage
- **Cost-effective**: Pay only for storage and requests
- **Scalable**: Cloudflare R2 handles scaling automatically
- **Schema flexibility**: JSON documents can evolve easily
- **Good fit for documents**: Dramas are self-contained documents

### Cons
- **No ACID transactions**: Cannot atomically update multiple dramas
- **Limited querying**: Can only list by prefix, no complex filters
- **Eventual consistency**: Potential race conditions on concurrent writes
- **Hash-based locking**: Current optimistic locking is custom implementation
- **No relational queries**: Cannot efficiently query by character name, genre, etc.
- **Full document reads**: Must read entire drama to check one field
- **Manual indexing**: No built-in indexes for search

## Proposed Architecture: Database (PostgreSQL/MySQL)

### Pros
- **ACID transactions**: Atomic updates across multiple tables
- **Row-level locking**: Built-in pessimistic/optimistic locking
- **Relational queries**: JOIN dramas with characters, episodes, scenes
- **Indexes**: Fast lookups by any field (title, genre, character names)
- **Partial updates**: Update single fields without reading entire drama
- **Referential integrity**: Foreign keys ensure data consistency
- **Mature tooling**: ORMs (SQLAlchemy), migrations (Alembic), monitoring
- **Complex queries**: Filter dramas by character count, episode length, etc.

### Cons
- **Infrastructure overhead**: Need to manage database server
- **Higher costs**: Database hosting more expensive than object storage
- **Connection pooling**: Need to manage connection limits
- **Schema migrations**: Changes require migration scripts
- **Scaling complexity**: Vertical scaling easier than horizontal
- **More complex setup**: Connection strings, credentials, backups

## Migration Strategy

### Option 1: Hybrid Approach (Recommended for MVP)
Keep R2 for storage, add database for metadata:
- **R2**: Store full drama JSON documents (current approach)
- **PostgreSQL**: Store drama metadata for queries (id, title, premise, created_at, updated_at)
- **Benefits**: Best of both worlds - simple storage + fast queries
- **Migration path**: Add database incrementally without rewriting storage layer

### Option 2: Full Database Migration
Move all data to relational tables:
- **dramas** table: id, title, description, premise, url, metadata
- **characters** table: id, drama_id, name, description, url, gender, voice
- **episodes** table: id, drama_id, title, description, order
- **scenes** table: id, episode_id, description, order
- **assets** table: id, entity_type, entity_id, kind, prompt, url, depends_on
- **Benefits**: Full relational queries, ACID transactions
- **Drawbacks**: Significant rewrite, joins needed for full drama

### Option 3: Database Primary, R2 as Cache (Best of Both Worlds)
Database as source of truth, R2 JSON as materialized view:
- **PostgreSQL**: Primary storage with full relational schema (tables for dramas, characters, episodes, scenes, assets)
- **R2**: Cached JSON copy of full drama, updated asynchronously after DB writes
- **Read flow**: Check R2 cache first → fallback to DB if cache miss → rebuild JSON from DB
- **Write flow**: Write to DB → queue background task to update R2 cache
- **Benefits**:
  - ACID transactions and row-level locking from database
  - Fast reads from R2 cache (no JOIN overhead)
  - Complex queries on database
  - Partial updates in database without reading full drama
  - Cache can be rebuilt from database if corrupted
  - Best read performance (cached JSON) + best write consistency (database)
- **Drawbacks**:
  - Cache invalidation complexity
  - Eventual consistency between DB and cache (acceptable for reads)
  - Need background workers for cache updates
  - More moving parts (database + cache + workers)

### Option 4: Keep R2, Improve Locking
Enhance current approach with better conflict resolution:
- Add ETag-based conditional writes (S3 native)
- Implement automatic retry with exponential backoff
- Add conflict resolution strategies (last-write-wins, merge, reject)
- **Benefits**: Minimal changes, keeps simplicity
- **Drawbacks**: Still limited querying, eventual consistency

## When to Migrate?

**Migrate when you need:**
- Complex queries (filter by character attributes, scene count, etc.)
- Strong consistency guarantees (financial data, user billing)
- Relational integrity (enforced foreign keys)
- Frequent partial updates (updating single fields)
- Real-time collaboration (multiple users editing same drama)

**Keep R2 if:**
- Read-heavy workload (dramas read more than written)
- Simple queries (list all, get by ID)
- Document-based model fits well
- Cost optimization is priority
- Serverless architecture preferred

## Current Trade-offs Accepted

1. **Hash-based optimistic locking** instead of database row locks
   - Acceptable: Drama generation jobs are infrequent, conflicts rare
   - Risk: If conflict occurs, job fails and must be retried manually

2. **Last-write-wins for asset additions** (add_asset_to_character)
   - Acceptable: Assets have unique IDs, duplicates filtered
   - Risk: Concurrent asset additions may lose one asset (low probability)

3. **No complex queries**
   - Current: Cannot filter dramas by character count, scene length, etc.
   - Acceptable: Frontend can filter after loading all dramas
   - Risk: Performance degrades as drama count grows (pagination helps)

4. **Full drama reads for any access**
   - Current: Must read entire JSON to check if drama exists
   - Acceptable: Drama documents are small (<1MB typically)
   - Risk: Bandwidth waste if only need metadata

## Architecture Comparison

| Aspect | Current (R2) | Option 1 (Hybrid Metadata) | Option 2 (Full DB) | Option 3 (DB + R2 Cache) |
|--------|-------------|---------------------------|-------------------|-------------------------|
| **Read Performance** | ⭐⭐⭐ Fast | ⭐⭐ Medium (needs JOIN) | ⭐⭐ Medium (needs JOIN) | ⭐⭐⭐⭐ Fastest (cache) |
| **Write Consistency** | ⭐ Hash-based | ⭐⭐ Metadata only | ⭐⭐⭐⭐ Full ACID | ⭐⭐⭐⭐ Full ACID |
| **Complex Queries** | ❌ None | ⭐⭐ Metadata only | ⭐⭐⭐⭐ Full queries | ⭐⭐⭐⭐ Full queries |
| **Partial Updates** | ❌ Full read/write | ❌ Full read/write | ⭐⭐⭐ Efficient | ⭐⭐⭐ Efficient |
| **Operational Cost** | ⭐⭐⭐⭐ Very low | ⭐⭐⭐ Low | ⭐⭐ Medium | ⭐ Higher (DB + cache) |
| **Complexity** | ⭐⭐⭐⭐ Simple | ⭐⭐⭐ Low | ⭐⭐ Medium | ⭐ High (cache sync) |
| **Migration Effort** | N/A | ⭐⭐⭐ Easy (additive) | ⭐ Hard (rewrite) | ⭐ Hard (full rewrite) |

## Recommendation

**For current stage (MVP/Beta):**
- ✅ Keep R2 for simplicity and cost (Current approach)
- ✅ Hash-based locking is sufficient for low-traffic
- ✅ Document model fits drama structure well
- ⚠️ Monitor for conflict frequency in production

**For growth stage (1k-10k dramas, moderate traffic):**
- 📊 Add Option 1: R2 storage + PostgreSQL metadata table
- 🔍 Metadata table for fast queries: `(id, title, created_at, character_count, genre)`
- ✅ Incremental migration, keeps R2 as source of truth
- 💰 Cost-effective, complexity manageable

**For production scale (>10k dramas, high concurrent writes):**
- 🚀 Implement Option 3: Database primary + R2 cache
- 🔒 ACID transactions eliminate hash-based conflicts
- ⚡ Best read performance from R2 cache
- 🔍 Complex queries and analytics on database
- ⚠️ Requires cache invalidation strategy and background workers
- 💡 Consider Option 2 (Full DB) if cache complexity not worth it

## Implementation Example: Option 3 (DB Primary + R2 Cache)

### Write Flow
```python
async def save_drama(drama: Drama):
    # 1. Write to database (source of truth)
    async with db.transaction():
        await db.dramas.upsert(drama.id, title=drama.title, ...)
        await db.characters.bulk_upsert(drama.characters)
        await db.episodes.bulk_upsert(drama.episodes)
        # ... etc

    # 2. Queue cache update (async, non-blocking)
    background_tasks.add_task(update_r2_cache, drama.id)

async def update_r2_cache(drama_id: str):
    # Rebuild JSON from database
    drama = await rebuild_drama_from_db(drama_id)
    # Upload to R2
    await r2.put_object(f"dramas/{drama_id}/drama.json", drama.json())
```

### Read Flow
```python
async def get_drama(drama_id: str) -> Drama:
    # 1. Try R2 cache first
    cached = await r2.get_object(f"dramas/{drama_id}/drama.json")
    if cached:
        return Drama.parse_raw(cached)

    # 2. Cache miss - rebuild from database
    drama = await rebuild_drama_from_db(drama_id)

    # 3. Update cache for next time (fire and forget)
    background_tasks.add_task(update_r2_cache, drama_id)

    return drama
```

### Benefits
- **Writes**: ACID transactions, no hash conflicts, partial updates
- **Reads**: Fast from R2 cache, fallback to DB if needed
- **Cache invalidation**: Simple - just delete R2 object on write
- **Cache rebuild**: Can rebuild entire cache from DB if corrupted

### Cache Update Race Conditions

**Problem**: Multiple workers updating cache concurrently can overwrite each other:
```
Worker A: Load v1 from DB → Generate JSON → Upload to R2
Worker B: Load v2 from DB → Generate JSON → Upload to R2 (overwrites A!)
```

**Impact**:
- ✅ Not critical: Database is source of truth, cache is just for speed
- ✅ Temporary: Next cache rebuild will fix stale data
- ⚠️ Wasted work: Workers duplicate effort
- ⚠️ Stale reads: Brief window of serving old cached data

**Solutions**:

1. **Debouncing (Recommended)**:
   ```python
   # Only update cache after 5 seconds of no writes
   await debounce_cache_update(drama_id, delay=5.0)
   ```
   - Pros: Coalesces rapid updates, reduces wasted work
   - Cons: Cache lags behind by debounce delay

2. **Cache Versioning**:
   ```python
   # Include DB updated_at timestamp in cache
   cache_meta = {"updated_at": drama.updated_at}

   # Skip cache update if stale
   current = await get_drama_from_db(drama_id)
   if current.updated_at > cache_meta["updated_at"]:
       return  # Newer version already cached
   ```
   - Pros: Avoids overwriting newer cache with stale data
   - Cons: Requires updated_at field in database

3. **Single Cache Worker**:
   ```python
   # Queue all cache updates to single dedicated worker
   redis.lpush("cache_update_queue", drama_id)
   ```
   - Pros: Serialized updates, no race conditions
   - Cons: Single point of failure, potential bottleneck

4. **Optimistic (Current)**:
   ```python
   # Accept last-write-wins, eventual consistency
   await r2.put_object(key, json)  # No coordination
   ```
   - Pros: Simple, no coordination overhead
   - Cons: Occasional stale cache, wasted worker cycles

**Recommendation**: Use **debouncing** for production scale. Cache staleness of 5-10 seconds is acceptable since database is authoritative.

## Implementation Checklist (if migrating)

### Option 1 (Metadata Only)
- [ ] Set up PostgreSQL instance
- [ ] Create single table: `drama_metadata(id, title, premise, created_at, character_count)`
- [ ] Add background task to sync metadata after R2 writes
- [ ] Add query endpoints using metadata table

### Option 2 or 3 (Full Database)
- [ ] Set up PostgreSQL instance (RDS, Render, Railway)
- [ ] Define database schema (tables, indexes, constraints)
- [ ] Add SQLAlchemy ORM models
- [ ] Implement migration scripts (Alembic)
- [ ] Add connection pooling (asyncpg, psycopg3)
- [ ] Migrate existing dramas from R2 to database
- [ ] Update storage layer to use database
- [ ] Add database backups
- [ ] Monitor query performance
- [ ] Update tests for database layer

### Option 3 Specific (Cache Layer)
- [ ] Implement cache invalidation strategy
- [ ] Add background workers for cache updates
- [ ] Add cache rebuild endpoint for manual refresh
- [ ] Monitor cache hit rate
- [ ] Add cache warming strategy (pre-populate popular dramas)

---

**Decision Date:** 2025-11-18
**Status:** Deferred - R2 approach working well for current scale
**Review Date:** When drama count exceeds 1000 or conflict rate exceeds 1%
