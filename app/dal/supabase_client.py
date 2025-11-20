"""
Supabase Client Connection Management

Provides singleton Supabase client with connection pooling and error handling.
Uses service role key for backend operations (bypasses RLS).
"""

import os
import logging
from typing import Optional
from supabase import create_client, Client
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Singleton Supabase client manager"""

    _instance: Optional[Client] = None
    _url: Optional[str] = None
    _key: Optional[str] = None

    @classmethod
    def initialize(cls, url: Optional[str] = None, key: Optional[str] = None):
        """
        Initialize Supabase client on app startup.

        Args:
            url: Supabase project URL (defaults to env var SUPABASE_URL)
            key: Service role key (defaults to env var SUPABASE_SERVICE_KEY)

        Raises:
            ValueError: If configuration is missing
        """
        cls._url = url or os.getenv("SUPABASE_URL")
        cls._key = key or os.getenv("SUPABASE_SERVICE_KEY")

        if not cls._url:
            raise ValueError(
                "SUPABASE_URL not configured. "
                "Set environment variable or pass to initialize()."
            )

        if not cls._key:
            raise ValueError(
                "SUPABASE_SERVICE_KEY not configured. "
                "Set environment variable or pass to initialize()."
            )

        logger.info(f"Initializing Supabase client for: {cls._url}")

        try:
            cls._instance = create_client(cls._url, cls._key)
            logger.info("✓ Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Supabase client: {e}")
            raise

    @classmethod
    def get_client(cls) -> Client:
        """
        Get Supabase client instance.

        Returns:
            Supabase client

        Raises:
            RuntimeError: If client not initialized
        """
        if cls._instance is None:
            # Auto-initialize from environment
            logger.warning(
                "Supabase client accessed before initialization. "
                "Auto-initializing from environment variables."
            )
            cls.initialize()

        return cls._instance

    @classmethod
    def close(cls):
        """Close Supabase client connection (if needed for cleanup)"""
        if cls._instance:
            logger.info("Closing Supabase client")
            cls._instance = None

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if client is initialized"""
        return cls._instance is not None

    @classmethod
    @asynccontextmanager
    async def transaction(cls):
        """
        Context manager for database transactions.

        Note: Supabase Python client doesn't have explicit transaction support.
        Use this for future-proofing if transaction support is added.
        For now, it just yields the client.

        Usage:
            async with SupabaseClient.transaction() as client:
                # Perform operations
                pass
        """
        client = cls.get_client()
        try:
            yield client
            # In future: commit transaction
        except Exception as e:
            # In future: rollback transaction
            logger.error(f"Transaction failed: {e}")
            raise


def get_supabase_client() -> Client:
    """
    Convenience function to get Supabase client.

    Returns:
        Supabase client instance
    """
    return SupabaseClient.get_client()


# Health check function
def check_supabase_connection() -> bool:
    """
    Test Supabase connection.

    Returns:
        True if connected, False otherwise
    """
    try:
        client = get_supabase_client()
        # Simple query to test connection
        client.table("users").select("id").limit(1).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase connection check failed: {e}")
        return False
