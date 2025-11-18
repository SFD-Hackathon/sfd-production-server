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

### Option 3: Keep R2, Improve Locking
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

## Recommendation

**For current stage (MVP/Beta):**
- ✅ Keep R2 for simplicity and cost
- ✅ Hash-based locking is sufficient for low-traffic
- ✅ Document model fits drama structure well
- ⚠️ Monitor for conflict frequency in production

**For production scale (>10k dramas, multiple concurrent users):**
- 📊 Consider hybrid approach (R2 storage + PostgreSQL metadata)
- 🔍 Add metadata table for fast queries: `(id, title, created_at, character_count)`
- 🔒 Evaluate conflict frequency to decide on full database migration
- 📈 Profile query performance to identify bottlenecks

## Implementation Checklist (if migrating)

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

---

**Decision Date:** 2025-11-18
**Status:** Deferred - R2 approach working well for current scale
**Review Date:** When drama count exceeds 1000 or conflict rate exceeds 1%
