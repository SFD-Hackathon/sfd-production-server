"""R2 Storage integration using S3-compatible API"""

import os
import json
import boto3
import asyncio
from botocore.config import Config
from typing import Optional, List, Dict, Any
from app.models import Drama


class R2Storage:
    """R2 Storage client for drama persistence"""

    def __init__(self):
        """Initialize R2 storage client"""
        # Lock for preventing concurrent writes to same drama
        self._drama_locks: Dict[str, asyncio.Lock] = {}
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

    def _get_drama_lock(self, drama_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific drama"""
        if drama_id not in self._drama_locks:
            self._drama_locks[drama_id] = asyncio.Lock()
        return self._drama_locks[drama_id]

    async def save_drama(self, drama: Drama) -> None:
        """
        Save drama to R2 storage
        Uses per-drama locking to prevent race conditions from concurrent writes.

        Args:
            drama: Drama object to save
        """
        # Acquire lock for this specific drama to prevent concurrent writes
        lock = self._get_drama_lock(drama.id)
        async with lock:
            key = self._get_drama_key(drama.id)
            drama_json = drama.model_dump_json(indent=2)

            self.s3_client.put_object(
                Bucket=self.bucket_name, Key=key, Body=drama_json, ContentType="application/json"
            )

    async def add_character_asset(self, drama_id: str, character_id: str, asset) -> None:
        """
        Atomically add an asset to a character
        Uses locking to prevent race conditions from concurrent updates.

        Args:
            drama_id: ID of the drama
            character_id: ID of the character
            asset: Asset object to add to the character
        """
        lock = self._get_drama_lock(drama_id)
        async with lock:
            # Load latest drama
            drama = await self.get_drama(drama_id)
            if not drama:
                raise Exception(f"Drama {drama_id} not found")

            # Find character and add asset
            character_found = False
            for char in drama.characters:
                if char.id == character_id:
                    # Check if asset already exists
                    existing_ids = {a.id for a in char.assets}
                    if asset.id not in existing_ids:
                        char.assets.append(asset)
                    character_found = True
                    break

            if not character_found:
                raise Exception(f"Character {character_id} not found in drama {drama_id}")

            # Save updated drama
            key = self._get_drama_key(drama_id)
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


# Global storage instance
storage = R2Storage()
