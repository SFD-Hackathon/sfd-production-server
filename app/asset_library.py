"""
AssetLibrary - Python Asset Management for R2 Storage

Manages images, videos, and text assets with metadata and caching support.
Provides user and project-based organization with comprehensive CRUD operations.
"""

import os
import json
import hashlib
import uuid
import re
import boto3
from typing import Optional, Dict, List, Any, Literal
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# R2 Storage Configuration
R2_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.getenv('R2_BUCKET', 'sfd-production')  # Updated to match destination env var
R2_ACCOUNT_ID = os.getenv('R2_ACCOUNT_ID')
R2_PUBLIC_URL = os.getenv('R2_PUBLIC_URL')

# Construct R2 endpoint URL
if R2_ACCOUNT_ID:
    R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
else:
    R2_ENDPOINT_URL = os.getenv('R2_ENDPOINT_URL')

# Type definitions
AssetType = Literal['image', 'video', 'text']
TagType = Literal['character', 'storyboard', 'clip']


class AssetNotFoundError(Exception):
    """Raised when an asset is not found in R2."""
    pass


class InvalidAssetTypeError(Exception):
    """Raised when an invalid asset type is provided."""
    pass


class InvalidTagError(Exception):
    """Raised when an invalid tag is provided."""
    pass


class AssetLibrary:
    """
    Manages R2 storage for user project assets with metadata and caching.

    Features:
    - User and project-based organization
    - Support for images, videos, and text assets
    - Tag-based classification (character, storyboard, clip)
    - Comprehensive metadata management
    - Project-scoped caching
    - CRUD operations with validation

    Usage:
        # Create library instance for a specific project
        lib = AssetLibrary(user_id="alice", project_name="detective_drama")

        # Upload an asset
        asset = lib.upload_asset(
            content=image_bytes,
            asset_type="image",
            tag="character",
            metadata={"prompt": "Detective character"}
        )

        # List assets
        assets = lib.list_assets(asset_type="image", tag="character")

        # Get asset
        content = lib.get_asset(asset_id="...", asset_type="image")
    """

    VALID_ASSET_TYPES = ['image', 'video', 'text']
    VALID_TAGS = ['character', 'storyboard', 'clip']
    ASSET_TYPE_EXTENSIONS = {
        'image': ['.png', '.jpg', '.jpeg', '.webp'],
        'video': ['.mp4'],
        'text': ['.txt']
    }

    def __init__(
        self,
        user_id: str,
        project_name: str,
        enabled: bool = True
    ):
        """
        Initialize AssetLibrary for a specific user project.

        Args:
            user_id: User identifier
            project_name: Project identifier
            enabled: Enable/disable caching (default: True)

        Raises:
            ValueError: If user_id or project_name is invalid
        """
        # Validate inputs
        if not user_id or not isinstance(user_id, str):
            raise ValueError("user_id must be a non-empty string")
        if not project_name or not isinstance(project_name, str):
            raise ValueError("project_name must be a non-empty string")

        self.user_id = self._sanitize_identifier(user_id)
        self.project_name = self._sanitize_identifier(project_name)
        self.enabled = enabled
        self._s3_client = None

    def _get_s3_client(self):
        """Lazy-load S3 client for R2 operations."""
        if not self._s3_client:
            self._s3_client = boto3.client(
                's3',
                endpoint_url=R2_ENDPOINT_URL,
                aws_access_key_id=R2_ACCESS_KEY_ID,
                aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                region_name='auto'
            )
        return self._s3_client

    def _sanitize_identifier(self, identifier: str) -> str:
        """
        Sanitize user_id or project_name for safe R2 paths.

        Args:
            identifier: String to sanitize

        Returns:
            Sanitized identifier (alphanumeric + underscores/hyphens)
        """
        # Replace spaces and special chars with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', identifier)
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        return sanitized.lower()

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for safe R2 storage.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Convert to lowercase
        name = filename.lower()
        # Replace special characters with underscores
        name = re.sub(r'[^a-z0-9._-]', '_', name)
        # Remove multiple consecutive underscores
        name = re.sub(r'_+', '_', name)
        # Remove leading/trailing underscores (but keep extension)
        parts = name.rsplit('.', 1)
        parts[0] = parts[0].strip('_')
        return '.'.join(parts) if len(parts) > 1 else parts[0]

    def _get_asset_folder(self, asset_type: str) -> str:
        """
        Get folder name for asset type.

        Args:
            asset_type: Type of asset ('image', 'video', 'text')

        Returns:
            Folder name (e.g., 'images', 'videos', 'texts')
        """
        return f"{asset_type}s"

    def _get_asset_path(
        self,
        asset_id: str,
        asset_type: str,
        ext: Optional[str] = None
    ) -> str:
        """
        Get full R2 path for an asset.

        Args:
            asset_id: Asset identifier
            asset_type: Type of asset
            ext: File extension (optional)

        Returns:
            Full R2 path: {user_id}/{project_name}/{asset_type}s/{asset_id}.{ext}
        """
        folder = self._get_asset_folder(asset_type)
        base_path = f"{self.user_id}/{self.project_name}/{folder}/{asset_id}"

        if ext:
            return f"{base_path}.{ext}"
        return base_path

    def _get_metadata_path(self, asset_id: str, asset_type: str) -> str:
        """
        Get R2 path for asset metadata file.

        Args:
            asset_id: Asset identifier
            asset_type: Type of asset

        Returns:
            Metadata path: {user_id}/{project_name}/{asset_type}s/{asset_id}.json
        """
        return self._get_asset_path(asset_id, asset_type, ext='json')

    def _get_cache_path(self, cache_key: str, ext: str) -> str:
        """
        Get R2 path for cache entry.

        Args:
            cache_key: Cache key identifier
            ext: File extension

        Returns:
            Cache path: {user_id}/{project_name}/_cache/{cache_key}.{ext}
        """
        return f"{self.user_id}/{self.project_name}/_cache/{cache_key}.{ext}"

    def _get_project_meta_path(self) -> str:
        """
        Get R2 path for project metadata.

        Returns:
            Project metadata path: {user_id}/{project_name}/meta/project.json
        """
        return f"{self.user_id}/{self.project_name}/meta/project.json"

    def _detect_content_type(self, filename: str, asset_type: str) -> str:
        """
        Detect MIME content type from filename and asset type.

        Args:
            filename: File name with extension
            asset_type: Type of asset

        Returns:
            MIME type string
        """
        ext = Path(filename).suffix.lower()

        # Image types
        if ext == '.png':
            return 'image/png'
        elif ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif ext == '.webp':
            return 'image/webp'

        # Video types
        elif ext == '.mp4':
            return 'video/mp4'

        # Text types
        elif ext == '.txt':
            return 'text/plain'

        # JSON
        elif ext == '.json':
            return 'application/json'

        # Default
        return 'application/octet-stream'

    def _validate_asset_type(self, asset_type: str) -> None:
        """
        Validate asset type.

        Args:
            asset_type: Asset type to validate

        Raises:
            InvalidAssetTypeError: If asset type is invalid
        """
        if asset_type not in self.VALID_ASSET_TYPES:
            raise InvalidAssetTypeError(
                f"Invalid asset_type '{asset_type}'. "
                f"Must be one of: {', '.join(self.VALID_ASSET_TYPES)}"
            )

    def _validate_tag(self, tag: str) -> None:
        """
        Validate tag.

        Args:
            tag: Tag to validate

        Raises:
            InvalidTagError: If tag is invalid
        """
        if tag not in self.VALID_TAGS:
            raise InvalidTagError(
                f"Invalid tag '{tag}'. "
                f"Must be one of: {', '.join(self.VALID_TAGS)}"
            )

    def _generate_asset_id(self) -> str:
        """
        Generate unique asset ID.

        Returns:
            UUID string
        """
        return str(uuid.uuid4())

    def _get_public_url(self, r2_key: str) -> str:
        """
        Get public CDN URL for R2 key.

        Args:
            r2_key: R2 object key

        Returns:
            Public URL
        """
        return f"{R2_PUBLIC_URL}/{r2_key}"

    def _ensure_project_exists(self) -> None:
        """
        Ensure project metadata exists in R2.
        Creates default project.json if it doesn't exist.
        """
        project_path = self._get_project_meta_path()
        s3_client = self._get_s3_client()

        try:
            # Check if project.json exists
            s3_client.head_object(Bucket=R2_BUCKET_NAME, Key=project_path)
        except Exception:
            # Project doesn't exist, create default metadata
            default_project = {
                "user_id": self.user_id,
                "project_name": self.project_name,
                "name": self.project_name.replace('_', ' ').title(),
                "created_at": datetime.utcnow().isoformat() + 'Z',
                "updated_at": datetime.utcnow().isoformat() + 'Z'
            }

            s3_client.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=project_path,
                Body=json.dumps(default_project, indent=2),
                ContentType='application/json'
            )

    # ===========================
    # CRUD Operations - Create
    # ===========================

    def upload_asset(
        self,
        content: bytes,
        asset_type: AssetType,
        tag: TagType,
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload an asset to R2 with metadata.

        Args:
            content: Asset content as bytes
            asset_type: Type of asset ('image', 'video', 'text')
            tag: Classification tag ('character', 'storyboard', 'clip')
            filename: Optional filename (default: auto-generated)
            metadata: Optional additional metadata

        Returns:
            Asset metadata dictionary

        Raises:
            InvalidAssetTypeError: If asset_type is invalid
            InvalidTagError: If tag is invalid
        """
        # Validate inputs
        self._validate_asset_type(asset_type)
        self._validate_tag(tag)

        # Ensure project exists
        self._ensure_project_exists()

        # Generate asset ID
        asset_id = self._generate_asset_id()

        # Determine file extension
        if filename:
            ext = Path(filename).suffix
        else:
            # Default extensions
            ext_map = {
                'image': '.png',
                'video': '.mp4',
                'text': '.txt'
            }
            ext = ext_map.get(asset_type, '')

        # Sanitize filename if provided
        if filename:
            sanitized_filename = self._sanitize_filename(filename)
        else:
            sanitized_filename = f"{asset_id}{ext}"

        # Build R2 path
        r2_key = self._get_asset_path(asset_id, asset_type, ext=ext.lstrip('.'))
        content_type = self._detect_content_type(sanitized_filename, asset_type)

        # Upload to R2
        s3_client = self._get_s3_client()
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=r2_key,
            Body=content,
            ContentType=content_type
        )

        # Create metadata
        asset_metadata = {
            "asset_id": asset_id,
            "user_id": self.user_id,
            "project_name": self.project_name,
            "asset_type": asset_type,
            "tag": tag,
            "filename": sanitized_filename,
            "created_at": datetime.utcnow().isoformat() + 'Z',
            "updated_at": datetime.utcnow().isoformat() + 'Z',
            "file_size": len(content),
            "r2_key": r2_key,
            "public_url": self._get_public_url(r2_key),
            "content_type": content_type
        }

        # Add custom metadata if provided
        if metadata:
            asset_metadata.update(metadata)

        # Save metadata to R2
        self._create_metadata(asset_id, asset_type, asset_metadata)

        return asset_metadata

    def upload_file(
        self,
        local_path: str,
        asset_type: AssetType,
        tag: TagType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload a local file to R2 as an asset.

        Args:
            local_path: Path to local file
            asset_type: Type of asset
            tag: Classification tag
            metadata: Optional additional metadata

        Returns:
            Asset metadata dictionary
        """
        # Read file
        with open(local_path, 'rb') as f:
            content = f.read()

        # Get filename from path
        filename = Path(local_path).name

        # Add original filename to metadata
        if metadata is None:
            metadata = {}
        metadata['original_filename'] = filename

        # Upload
        return self.upload_asset(
            content=content,
            asset_type=asset_type,
            tag=tag,
            filename=filename,
            metadata=metadata
        )

    # ===========================
    # CRUD Operations - Read
    # ===========================

    def get_asset(self, asset_id: str, asset_type: AssetType) -> bytes:
        """
        Retrieve asset content from R2.

        Args:
            asset_id: Asset identifier
            asset_type: Type of asset

        Returns:
            Asset content as bytes

        Raises:
            AssetNotFoundError: If asset doesn't exist
        """
        self._validate_asset_type(asset_type)

        # Get metadata to find actual file extension
        metadata = self.get_metadata(asset_id, asset_type)
        r2_key = metadata['r2_key']

        # Fetch from R2
        s3_client = self._get_s3_client()
        try:
            response = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
            return response['Body'].read()
        except Exception as e:
            raise AssetNotFoundError(
                f"Asset not found: {asset_id} ({asset_type})"
            ) from e

    def get_asset_url(self, asset_id: str, asset_type: AssetType) -> str:
        """
        Get public URL for an asset.

        Args:
            asset_id: Asset identifier
            asset_type: Type of asset

        Returns:
            Public CDN URL
        """
        metadata = self.get_metadata(asset_id, asset_type)
        return metadata['public_url']

    def list_assets(
        self,
        asset_type: Optional[AssetType] = None,
        tag: Optional[TagType] = None
    ) -> List[Dict[str, Any]]:
        """
        List assets in the current project.

        Args:
            asset_type: Optional filter by asset type
            tag: Optional filter by tag

        Returns:
            List of asset metadata dictionaries
        """
        # Validate filters
        if asset_type:
            self._validate_asset_type(asset_type)
        if tag:
            self._validate_tag(tag)

        s3_client = self._get_s3_client()
        assets = []

        # Determine which folders to search
        if asset_type:
            folders = [self._get_asset_folder(asset_type)]
        else:
            folders = [self._get_asset_folder(t) for t in self.VALID_ASSET_TYPES]

        # List objects in each folder
        for folder in folders:
            prefix = f"{self.user_id}/{self.project_name}/{folder}/"

            try:
                paginator = s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(
                    Bucket=R2_BUCKET_NAME,
                    Prefix=prefix
                )

                for page in pages:
                    if 'Contents' not in page:
                        continue

                    for obj in page['Contents']:
                        key = obj['Key']

                        # Only process metadata files
                        if not key.endswith('.json'):
                            continue

                        # Fetch and parse metadata
                        try:
                            meta_obj = s3_client.get_object(
                                Bucket=R2_BUCKET_NAME,
                                Key=key
                            )
                            metadata = json.loads(meta_obj['Body'].read())

                            # Apply tag filter
                            if tag and metadata.get('tag') != tag:
                                continue

                            assets.append(metadata)

                        except Exception:
                            # Skip invalid metadata files
                            continue

            except Exception:
                # Folder doesn't exist or error listing
                continue

        return assets

    # ===========================
    # CRUD Operations - Delete
    # ===========================

    def delete_asset(self, asset_id: str, asset_type: AssetType) -> bool:
        """
        Delete an asset and its metadata from R2.

        Args:
            asset_id: Asset identifier
            asset_type: Type of asset

        Returns:
            True if successful

        Raises:
            AssetNotFoundError: If asset doesn't exist
        """
        self._validate_asset_type(asset_type)

        # Get metadata to find R2 key
        metadata = self.get_metadata(asset_id, asset_type)
        r2_key = metadata['r2_key']
        metadata_key = self._get_metadata_path(asset_id, asset_type)

        s3_client = self._get_s3_client()

        # Delete asset file
        s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=r2_key)

        # Delete metadata file
        s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=metadata_key)

        return True

    # ===========================
    # Metadata Operations
    # ===========================

    def get_metadata(self, asset_id: str, asset_type: AssetType) -> Dict[str, Any]:
        """
        Retrieve asset metadata from R2.

        Args:
            asset_id: Asset identifier
            asset_type: Type of asset

        Returns:
            Metadata dictionary

        Raises:
            AssetNotFoundError: If metadata doesn't exist
        """
        self._validate_asset_type(asset_type)

        metadata_key = self._get_metadata_path(asset_id, asset_type)
        s3_client = self._get_s3_client()

        try:
            response = s3_client.get_object(
                Bucket=R2_BUCKET_NAME,
                Key=metadata_key
            )
            metadata = json.loads(response['Body'].read())
            return metadata
        except Exception as e:
            raise AssetNotFoundError(
                f"Metadata not found for asset: {asset_id} ({asset_type})"
            ) from e

    def update_metadata(
        self,
        asset_id: str,
        asset_type: AssetType,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update asset metadata.

        Args:
            asset_id: Asset identifier
            asset_type: Type of asset
            updates: Dictionary of fields to update

        Returns:
            Updated metadata dictionary

        Raises:
            AssetNotFoundError: If metadata doesn't exist
        """
        # Get existing metadata
        metadata = self.get_metadata(asset_id, asset_type)

        # Apply updates
        metadata.update(updates)
        metadata['updated_at'] = datetime.utcnow().isoformat() + 'Z'

        # Save to R2
        metadata_key = self._get_metadata_path(asset_id, asset_type)
        s3_client = self._get_s3_client()

        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=metadata_key,
            Body=json.dumps(metadata, indent=2),
            ContentType='application/json'
        )

        return metadata

    def _create_metadata(
        self,
        asset_id: str,
        asset_type: AssetType,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create new metadata file in R2.

        Args:
            asset_id: Asset identifier
            asset_type: Type of asset
            metadata: Metadata dictionary

        Returns:
            Metadata dictionary
        """
        metadata_key = self._get_metadata_path(asset_id, asset_type)
        s3_client = self._get_s3_client()

        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=metadata_key,
            Body=json.dumps(metadata, indent=2),
            ContentType='application/json'
        )

        return metadata
