"""
Asset Library API Router
Global asset management endpoints for R2 storage
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from app.dependencies import verify_api_key
from app.asset_library import AssetLibrary, AssetNotFoundError, InvalidAssetTypeError, InvalidTagError

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/list")
async def list_assets(
    user_id: str = "10000",
    project_name: Optional[str] = None,
    asset_type: Optional[str] = None,
    tag: Optional[str] = None
):
    """
    List assets with filters

    Query parameters:
    - user_id: User identifier (default: "10000")
    - project_name: Project name (required)
    - asset_type: Filter by type ("image" | "video" | "text")
    - tag: Filter by tag ("character" | "storyboard" | "clip")

    Returns:
        List of asset metadata
    """
    if not project_name:
        raise HTTPException(status_code=400, detail="project_name is required")

    try:
        lib = AssetLibrary(user_id=user_id, project_name=project_name)
        assets = lib.list_assets(asset_type=asset_type, tag=tag)

        return {
            "assets": assets,
            "total": len(assets),
            "user_id": user_id,
            "project_name": project_name
        }
    except (InvalidAssetTypeError, InvalidTagError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list assets: {str(e)}")


@router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    user_id: str = Form("10000"),
    project_name: str = Form(...),
    asset_type: str = Form(...),
    tag: str = Form(...),
    metadata: Optional[str] = Form(None)
):
    """
    Upload an asset directly to R2

    Form data:
    - file: File to upload
    - user_id: User identifier (default: "10000")
    - project_name: Project name
    - asset_type: Asset type ("image" | "video" | "text")
    - tag: Classification tag ("character" | "storyboard" | "clip")
    - metadata: JSON string of additional metadata (optional)

    Returns:
        Asset metadata with public URL
    """
    try:
        # Read file content
        content = await file.read()

        # Parse metadata if provided
        import json
        metadata_dict = json.loads(metadata) if metadata else {}

        # Upload to R2
        lib = AssetLibrary(user_id=user_id, project_name=project_name)
        asset_metadata = lib.upload_asset(
            content=content,
            asset_type=asset_type,
            tag=tag,
            filename=file.filename,
            metadata=metadata_dict
        )

        return {
            "asset_id": asset_metadata["asset_id"],
            "asset_type": asset_metadata["asset_type"],
            "tag": asset_metadata["tag"],
            "r2_key": asset_metadata["r2_key"],
            "public_url": asset_metadata["public_url"],
            "created_at": asset_metadata["created_at"]
        }
    except (InvalidAssetTypeError, InvalidTagError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload asset: {str(e)}")


@router.get("/{asset_id}")
async def get_asset(
    asset_id: str,
    user_id: str = "10000",
    project_name: str = None,
    asset_type: str = None
):
    """
    Download asset content from R2

    Path parameters:
    - asset_id: Asset identifier

    Query parameters:
    - user_id: User identifier (default: "10000")
    - project_name: Project name (required)
    - asset_type: Asset type ("image" | "video" | "text") (required)

    Returns:
        Asset content with appropriate Content-Type header
    """
    if not project_name or not asset_type:
        raise HTTPException(status_code=400, detail="project_name and asset_type are required")

    try:
        lib = AssetLibrary(user_id=user_id, project_name=project_name)
        content = lib.get_asset(asset_id, asset_type)
        metadata = lib.get_metadata(asset_id, asset_type)

        from fastapi.responses import Response
        return Response(
            content=content,
            media_type=metadata.get("content_type", "application/octet-stream")
        )
    except AssetNotFoundError:
        raise HTTPException(status_code=404, detail="Asset not found")
    except (InvalidAssetTypeError, InvalidTagError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get asset: {str(e)}")


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: str,
    user_id: str = "10000",
    project_name: str = None,
    asset_type: str = None
):
    """
    Delete an asset from R2

    Path parameters:
    - asset_id: Asset identifier

    Query parameters:
    - user_id: User identifier (default: "10000")
    - project_name: Project name (required)
    - asset_type: Asset type ("image" | "video" | "text") (required)

    Returns:
        Success message
    """
    if not project_name or not asset_type:
        raise HTTPException(status_code=400, detail="project_name and asset_type are required")

    try:
        lib = AssetLibrary(user_id=user_id, project_name=project_name)
        lib.delete_asset(asset_id, asset_type)

        return {
            "success": True,
            "message": "Asset deleted successfully"
        }
    except AssetNotFoundError:
        raise HTTPException(status_code=404, detail="Asset not found")
    except (InvalidAssetTypeError, InvalidTagError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete asset: {str(e)}")


@router.get("/{asset_id}/metadata")
async def get_asset_metadata(
    asset_id: str,
    user_id: str = "10000",
    project_name: str = None,
    asset_type: str = None
):
    """
    Get asset metadata only (without downloading content)

    Path parameters:
    - asset_id: Asset identifier

    Query parameters:
    - user_id: User identifier (default: "10000")
    - project_name: Project name (required)
    - asset_type: Asset type ("image" | "video" | "text") (required)

    Returns:
        Asset metadata
    """
    if not project_name or not asset_type:
        raise HTTPException(status_code=400, detail="project_name and asset_type are required")

    try:
        lib = AssetLibrary(user_id=user_id, project_name=project_name)
        metadata = lib.get_metadata(asset_id, asset_type)

        return metadata
    except AssetNotFoundError:
        raise HTTPException(status_code=404, detail="Asset not found")
    except (InvalidAssetTypeError, InvalidTagError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")
