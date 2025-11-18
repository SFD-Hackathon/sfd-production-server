"""R2 Storage integration using S3-compatible API"""

import os
import json
import boto3
from botocore.config import Config
from typing import Optional, List, Dict, Any, Tuple
from app.models import Drama, Asset


class StorageConflictError(Exception):
    """Raised when attempting to save a drama that has been modified by another process"""
    pass


class R2Storage:
    """R2 Storage client for drama persistence"""

    def __init__(self):
        """Initialize R2 storage client"""
        # R2 credentials from environment
        account_id = os.getenv("R2_ACCOUNT_ID")
        access_key_id = os.getenv("R2_ACCESS_KEY_ID")
        secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("R2_BUCKET", "sfd-production")
        self.public_url_base = os.getenv("R2_PUBLIC_URL", "https://pub-82a9c3c68d1a421f8e31796087e04132.r2.dev")

        # Construct R2 endpoint
        if account_id:
            endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        else:
            # Fallback for local development
            endpoint_url = os.getenv("R2_ENDPOINT_URL", "http://localhost:9000")

        # Create S3 client configured for R2
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",  # R2 uses 'auto' region
        )

    def _get_drama_key(self, drama_id: str) -> str:
        """Get S3 key for drama object"""
        return f"dramas/{drama_id}/drama.json"

    def _compute_drama_hash(self, drama: Drama) -> str:
        """
        Compute hash of drama content for optimistic locking

        Args:
            drama: Drama object to hash

        Returns:
            SHA256 hash of drama JSON content
        """
        # Use compact JSON (no indent) for consistent hashing
        drama_json = drama.model_dump_json()
        return hashlib.sha256(drama_json.encode()).hexdigest()

    async def get_current_hash_from_id(self, drama_id: str) -> Optional[str]:
        """
        Get current hash of a drama by ID

        Args:
            drama_id: ID of the drama

        Returns:
            SHA256 hash of current drama, or None if drama doesn't exist
        """
        current_drama = await self.get_drama(drama_id)
        if current_drama:
            return self._compute_drama_hash(current_drama)
        return None

    async def save_drama(self, drama: Drama, expected_hash: Optional[str] = None) -> None:
        """
        Save drama to R2 storage with optional optimistic locking

        Args:
            drama: Drama object to save
            expected_hash: Expected hash of current stored drama (for conflict detection)

        Raises:
            StorageConflictError: If expected_hash is provided and doesn't match current stored version
        """
        key = self._get_drama_key(drama.id)

        # Optimistic locking: verify hash if provided
        if expected_hash is not None:
            try:
                current_drama = await self.get_drama(drama.id)
                if current_drama:
                    current_hash = self._compute_drama_hash(current_drama)
                    if current_hash != expected_hash:
                        raise StorageConflictError(
                            f"Drama {drama.id} was modified by another process. "
                            f"Expected hash {expected_hash[:8]}..., got {current_hash[:8]}..."
                        )
            except StorageConflictError:
                raise
            except Exception as e:
                # If we can't verify hash, log warning but proceed
                print(f"Warning: Could not verify drama hash: {e}")

        drama_json = drama.model_dump_json(indent=2)

        self.s3_client.put_object(
            Bucket=self.bucket_name, Key=key, Body=drama_json, ContentType="application/json"
        )

    async def get_drama(self, drama_id: str) -> Optional[Drama]:
        """
        Retrieve drama from R2 storage

        Args:
            drama_id: ID of drama to retrieve

        Returns:
            Drama object if found, None otherwise
        """
        try:
            key = self._get_drama_key(drama_id)
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            drama_data = json.loads(response["Body"].read())
            return Drama(**drama_data)
        except self.s3_client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            print(f"Error retrieving drama {drama_id}: {e}")
            return None

    async def delete_drama(self, drama_id: str) -> bool:
        """
        Delete drama from R2 storage

        Args:
            drama_id: ID of drama to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            key = self._get_drama_key(drama_id)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as e:
            print(f"Error deleting drama {drama_id}: {e}")
            return False

    async def list_dramas(self, limit: int = 100, cursor: Optional[str] = None) -> tuple[List[Drama], Optional[str]]:
        """
        List dramas with pagination

        Args:
            limit: Maximum number of dramas to return
            cursor: Pagination cursor (continuation token)

        Returns:
            Tuple of (list of dramas, next cursor)
        """
        try:
            # List objects with pagination
            list_kwargs = {
                "Bucket": self.bucket_name,
                "Prefix": "dramas/",
                "MaxKeys": limit,
            }

            if cursor:
                list_kwargs["ContinuationToken"] = cursor

            response = self.s3_client.list_objects_v2(**list_kwargs)

            # Get drama objects
            dramas = []
            if "Contents" in response:
                for obj in response["Contents"]:
                    try:
                        drama_response = self.s3_client.get_object(Bucket=self.bucket_name, Key=obj["Key"])
                        drama_data = json.loads(drama_response["Body"].read())
                        dramas.append(Drama(**drama_data))
                    except Exception as e:
                        print(f"Error loading drama from {obj['Key']}: {e}")
                        continue

            # Get next cursor
            next_cursor = response.get("NextContinuationToken")

            return dramas, next_cursor

        except Exception as e:
            print(f"Error listing dramas: {e}")
            return [], None

    def upload_image(self, image_data: bytes, drama_id: str, character_id: str) -> str:
        """
        Upload character image to R2 storage

        Args:
            image_data: Image binary data
            drama_id: ID of the drama
            character_id: ID of the character

        Returns:
            Public URL of the uploaded image
        """
        key = f"dramas/{drama_id}/characters/{character_id}.png"

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=image_data,
            ContentType="image/png",
        )

        # Return public URL
        return f"{self.public_url_base}/{key}"

    async def drama_exists(self, drama_id: str) -> bool:
        """
        Check if drama exists in storage

        Args:
            drama_id: ID of drama to check

        Returns:
            True if exists, False otherwise
        """
        try:
            key = self._get_drama_key(drama_id)
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except self.s3_client.exceptions.NoSuchKey:
            return False
        except Exception:
            return False

    async def add_asset_to_character(self, drama_id: str, character_id: str, asset: Asset) -> None:
        """
        Add an asset to a character by reloading latest drama

        Simple reload-append-save pattern. No conflict detection - if concurrent
        modifications occur, last write wins. This is acceptable for asset additions
        since assets have unique IDs and duplicates are filtered.

        Args:
            drama_id: ID of the drama
            character_id: ID of the character
            asset: Asset to add to character

        Raises:
            Exception: If drama or character not found
        """
        # Reload fresh drama
        drama = await self.get_drama(drama_id)
        if not drama:
            raise Exception(f"Drama {drama_id} not found")

        # Find character
        character = None
        for char in drama.characters:
            if char.id == character_id:
                character = char
                break

        if not character:
            raise Exception(f"Character {character_id} not found in drama {drama_id}")

        # Check if asset already exists
        existing_ids = {a.id for a in character.assets}
        if asset.id not in existing_ids:
            character.assets.append(asset)

        # Save updated drama (no hash verification)
        await self.save_drama(drama)


# Global storage instance
storage = R2Storage()

# Export for use by other modules
__all__ = ["storage", "R2Storage", "StorageConflictError"]
