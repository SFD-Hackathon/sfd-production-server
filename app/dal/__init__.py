"""
Data Access Layer (DAL) Module

Provides repository pattern for database operations with Supabase.

Architecture:
- Repositories: Data access logic (CRUD operations)
- Services: Business logic (uses repositories)
- GraphQL/REST: API layer (uses services)

Example:
    from app.dal.job_repository import JobRepository
    from app.dal.supabase_client import get_supabase_client

    client = get_supabase_client()
    job_repo = JobRepository(client)
    job = await job_repo.create_job(...)
"""

from app.dal.supabase_client import get_supabase_client, SupabaseClient
from app.dal.base import BaseRepository
from app.dal.job_repository import JobRepository
from app.dal.drama_repository import DramaRepository
from app.dal.user_repository import UserRepository

__all__ = [
    "get_supabase_client",
    "SupabaseClient",
    "BaseRepository",
    "JobRepository",
    "DramaRepository",
    "UserRepository",
]
