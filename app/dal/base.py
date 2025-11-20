"""
Base Repository Class

Provides common database operations and patterns for all repositories.
"""

import logging
from typing import Dict, List, Optional, Any
from supabase import Client
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseRepository:
    """
    Base repository with common CRUD operations.

    All repository classes should inherit from this base.
    """

    def __init__(self, client: Client, table_name: str):
        """
        Initialize repository.

        Args:
            client: Supabase client instance
            table_name: Name of the database table
        """
        self.client = client
        self.table_name = table_name
        self.table = client.table(table_name)

    async def find_by_id(self, id_column: str, id_value: Any) -> Optional[Dict]:
        """
        Find a single record by ID.

        Args:
            id_column: Name of the ID column
            id_value: Value to search for

        Returns:
            Record dict or None if not found
        """
        try:
            response = self.table.select("*").eq(id_column, id_value).maybe_single().execute()
            return response.data
        except Exception as e:
            logger.error(f"Error finding {self.table_name} by {id_column}={id_value}: {e}")
            return None

    async def find_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None,
        ascending: bool = False,
    ) -> List[Dict]:
        """
        Find all records matching filters.

        Args:
            filters: Dictionary of column:value pairs to filter by
            limit: Maximum number of records to return
            offset: Number of records to skip
            order_by: Column to sort by
            ascending: Sort direction

        Returns:
            List of record dicts
        """
        try:
            query = self.table.select("*")

            # Apply filters
            if filters:
                for column, value in filters.items():
                    query = query.eq(column, value)

            # Apply ordering
            if order_by:
                query = query.order(order_by, desc=not ascending)

            # Apply pagination
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)

            response = query.execute()
            return response.data
        except Exception as e:
            logger.error(f"Error finding {self.table_name} records: {e}")
            return []

    async def create(self, data: Dict[str, Any]) -> Optional[Dict]:
        """
        Create a new record.

        Args:
            data: Record data to insert

        Returns:
            Created record dict or None if failed
        """
        try:
            # Add timestamp if not provided
            if "created_at" not in data:
                data["created_at"] = datetime.utcnow().isoformat()

            response = self.table.insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating {self.table_name} record: {e}")
            logger.error(f"Data: {data}")
            return None

    async def update(
        self,
        id_column: str,
        id_value: Any,
        data: Dict[str, Any]
    ) -> Optional[Dict]:
        """
        Update a record by ID.

        Args:
            id_column: Name of the ID column
            id_value: Value to match
            data: Fields to update

        Returns:
            Updated record dict or None if failed
        """
        try:
            # Add update timestamp
            if "updated_at" not in data:
                data["updated_at"] = datetime.utcnow().isoformat()

            response = self.table.update(data).eq(id_column, id_value).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating {self.table_name} by {id_column}={id_value}: {e}")
            return None

    async def delete(self, id_column: str, id_value: Any) -> bool:
        """
        Delete a record by ID.

        Args:
            id_column: Name of the ID column
            id_value: Value to match

        Returns:
            True if successful, False otherwise
        """
        try:
            self.table.delete().eq(id_column, id_value).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting {self.table_name} by {id_column}={id_value}: {e}")
            return False

    async def upsert(self, data: Dict[str, Any]) -> Optional[Dict]:
        """
        Insert or update a record (upsert).

        Args:
            data: Record data

        Returns:
            Upserted record dict or None if failed
        """
        try:
            response = self.table.upsert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error upserting {self.table_name} record: {e}")
            return None

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records matching filters.

        Args:
            filters: Dictionary of column:value pairs to filter by

        Returns:
            Count of matching records
        """
        try:
            query = self.table.select("id", count="exact")

            # Apply filters
            if filters:
                for column, value in filters.items():
                    query = query.eq(column, value)

            response = query.execute()
            return response.count if response.count is not None else 0
        except Exception as e:
            logger.error(f"Error counting {self.table_name} records: {e}")
            return 0

    async def exists(self, id_column: str, id_value: Any) -> bool:
        """
        Check if a record exists.

        Args:
            id_column: Name of the ID column
            id_value: Value to check

        Returns:
            True if record exists, False otherwise
        """
        record = await self.find_by_id(id_column, id_value)
        return record is not None
