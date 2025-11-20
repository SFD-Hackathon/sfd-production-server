"""
User Repository

Data access layer for user-related operations and authentication.
"""

import logging
from typing import Dict, List, Optional
from supabase import Client
from app.dal.base import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """Repository for user table operations"""

    def __init__(self, client: Client):
        super().__init__(client, "users")

    async def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        return await self.find_by_id("id", user_id)

    async def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        return await self.find_by_id("email", email)

    async def create_user(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str] = None,
        tokens: int = 30,
    ) -> Optional[Dict]:
        """
        Create a new user.

        Args:
            user_id: User ID (from auth.users)
            email: User email
            display_name: Optional display name
            tokens: Initial token balance (default: 30)

        Returns:
            Created user record or None if failed
        """
        user_data = {
            "id": user_id,
            "email": email,
            "tokens": tokens,
            "subscription_tier": "free",
        }

        if display_name:
            user_data["display_name"] = display_name

        return await self.create(user_data)

    async def update_tokens(
        self,
        user_id: str,
        tokens: int
    ) -> Optional[Dict]:
        """Update user token balance"""
        return await self.update("id", user_id, {"tokens": tokens})

    async def update_subscription_tier(
        self,
        user_id: str,
        tier: str
    ) -> Optional[Dict]:
        """Update user subscription tier"""
        return await self.update("id", user_id, {"subscription_tier": tier})

    # ==========================================================================
    # API Key Management (for backend authentication)
    # ==========================================================================

    # Note: For now, we'll use a simple mapping. In production, create a
    # separate api_keys table with proper key rotation and expiration.

    async def validate_api_key(self, api_key: str) -> Optional[str]:
        """
        Validate API key and return user_id.

        For now, this is a placeholder. In production:
        1. Create api_keys table
        2. Store hashed keys
        3. Implement key rotation
        4. Add rate limiting

        Args:
            api_key: API key to validate

        Returns:
            User ID if valid, None otherwise
        """
        # TODO: Implement proper API key validation
        # For now, return a default user_id for testing
        logger.warning(
            "Using placeholder API key validation. "
            "Implement proper API key table in production."
        )

        # Placeholder: Return first user for any valid-looking key
        if api_key and len(api_key) > 10:
            users = await self.find_all(limit=1)
            return users[0]["id"] if users else None

        return None
