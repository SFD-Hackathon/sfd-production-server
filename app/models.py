"""Data models for Drama API"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class AssetKind(str, Enum):
    """Asset type enumeration"""
    image = "image"
    video = "video"


class JobType(str, Enum):
    """Job type enumeration"""
    generate_drama = "generate_drama"
    improve_drama = "improve_drama"
    generate_image = "generate_image"
    generate_video = "generate_video"
    generate_audio = "generate_audio"


class JobStatus(str, Enum):
    """Job status enumeration"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# Asset models
class Asset(BaseModel):
    """Asset schema"""
    id: str = Field(..., description="Unique identifier for the asset")
    kind: AssetKind = Field(..., description="Type of asset")
    depends_on: List[str] = Field(default_factory=list, description="IDs of assets this asset depends on")
    prompt: str = Field(..., description="Prompt used to generate the asset")
    duration: Optional[int] = Field(None, description="Duration in seconds (10 or 15 for video assets, null for image)")
    url: Optional[str] = Field(None, description="URL to the generated asset")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the asset")


# Scene models
class Scene(BaseModel):
    """Scene schema"""
    id: str = Field(..., description="Unique identifier for the scene")
    description: str = Field(..., description="Scene description")
    image_url: Optional[str] = Field(None, description="URL to scene image")
    video_url: Optional[str] = Field(None, description="URL to scene video")
    assets: List[Asset] = Field(default_factory=list, description="Scene assets")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the scene")


# Episode models
class Episode(BaseModel):
    """Episode schema"""
    id: str = Field(..., description="Unique identifier for the episode")
    title: str = Field(..., description="Episode title")
    description: str = Field(..., description="Episode description")
    premise: Optional[str] = Field(None, description="Episode-specific premise")
    url: Optional[str] = Field(None, description="URL to episode resource")
    scenes: List[Scene] = Field(default_factory=list, description="Episode scenes")
    assets: List[Asset] = Field(default_factory=list, description="Episode assets")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the episode")


# Character models
class Character(BaseModel):
    """Character schema"""
    id: str = Field(..., description="Unique identifier for the character")
    name: str = Field(..., description="Character name")
    description: str = Field(..., description="Character description")
    gender: str = Field(..., description="Character gender (male/female/other)")
    main: bool = Field(default=False, description="Whether this is a main character")
    url: Optional[str] = Field(None, description="URL to character image")
    premise_url: Optional[str] = Field(None, description="URL to character premise image")
    assets: List[Asset] = Field(default_factory=list, description="Character assets")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the character")


# Drama models
class Drama(BaseModel):
    """Drama schema"""
    id: str = Field(..., description="Unique identifier for the drama")
    title: str = Field(..., description="Title of the drama")
    description: str = Field(..., description="Brief description of the drama")
    premise: str = Field(..., description="Original premise used to generate the drama")
    url: Optional[str] = Field(None, description="Optional URL to drama resource")
    characters: List[Character] = Field(default_factory=list, description="Drama characters")
    episodes: List[Episode] = Field(default_factory=list, description="Drama episodes")
    assets: List[Asset] = Field(default_factory=list, description="Drama assets")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the drama")


class DramaSummary(BaseModel):
    """Drama summary schema (lightweight version without nested data)"""
    id: str = Field(..., description="Unique identifier for the drama")
    title: str = Field(..., description="Title of the drama")
    description: str = Field(..., description="Brief description of the drama")
    premise: str = Field(..., description="Original premise used to generate the drama")
    url: Optional[str] = Field(None, description="Optional URL to drama resource")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the drama")


# Request models
class CreateFromPremise(BaseModel):
    """Create drama from text premise"""
    premise: str = Field(..., description="Text premise to generate drama from")
    id: Optional[str] = Field(None, description="Optional custom ID for the drama")


class CreateFromJSON(BaseModel):
    """Create drama from complete JSON object"""
    drama: Drama = Field(..., description="Complete drama object")


class ImproveDramaRequest(BaseModel):
    """Request to improve a drama"""
    feedback: str = Field(..., description="Feedback for improving the drama")


# Response models
class JobResponse(BaseModel):
    """Job creation response"""
    dramaId: str = Field(..., description="ID of the drama being generated")
    jobId: str = Field(..., description="ID of the generation job")
    status: JobStatus = Field(..., description="Current job status")
    message: str = Field(..., description="Instructions for checking job status")


class JobStatusRecord(BaseModel):
    """Job status record"""
    jobId: str = Field(..., description="Unique identifier for the job")
    type: JobType = Field(..., description="Type of job")
    status: JobStatus = Field(..., description="Current job status")
    dramaId: str = Field(..., description="ID of the associated drama")
    createdAt: int = Field(..., description="Timestamp when job was created (milliseconds since epoch)")
    startedAt: Optional[int] = Field(None, description="Timestamp when job started processing")
    completedAt: Optional[int] = Field(None, description="Timestamp when job completed")
    error: Optional[str] = Field(None, description="Error message if job failed")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result data (varies by job type)")


class ImproveDramaResponse(BaseModel):
    """Response for improve drama endpoint"""
    originalId: str
    improvedId: str
    jobId: str
    status: JobStatus
    message: str


class ErrorResponse(BaseModel):
    """Error response"""
    error: str = Field(..., description="Error message")
    message: Optional[str] = Field(None, description="Detailed error message")


# Update models
class DramaUpdate(BaseModel):
    """Drama update schema"""
    title: Optional[str] = None
    description: Optional[str] = None
    premise: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CharacterUpdate(BaseModel):
    """Character update schema"""
    name: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class EpisodeUpdate(BaseModel):
    """Episode update schema"""
    title: Optional[str] = None
    description: Optional[str] = None
    premise: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SceneUpdate(BaseModel):
    """Scene update schema"""
    description: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AssetUpdate(BaseModel):
    """Asset update schema"""
    prompt: Optional[str] = None
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# List response models
class DramaListResponse(BaseModel):
    """Response for listing dramas (summary view)"""
    dramas: List[DramaSummary]
    cursor: Optional[str] = None


class CharacterListResponse(BaseModel):
    """Response for listing characters"""
    characters: List[Character]


class EpisodeListResponse(BaseModel):
    """Response for listing episodes"""
    episodes: List[Episode]


class SceneListResponse(BaseModel):
    """Response for listing scenes"""
    scenes: List[Scene]


class AssetListResponse(BaseModel):
    """Response for listing assets"""
    assets: List[Asset]


class JobListResponse(BaseModel):
    """Response for listing jobs"""
    jobs: List[JobStatusRecord]


# ============================================================================
# Lite models for LLM generation (simplified schema with only required fields)
# ============================================================================

class AssetLite(BaseModel):
    """Simplified asset schema for LLM generation"""
    id: str = Field(..., description="Unique identifier for the asset")
    kind: AssetKind = Field(..., description="Type of asset (image or video)")
    prompt: str = Field(..., description="Detailed prompt for generating this asset")
    duration: Optional[int] = Field(None, description="Duration in seconds (10 or 15 for video, null for image)")


class SceneLite(BaseModel):
    """Simplified scene schema for LLM generation"""
    id: str = Field(..., description="Unique identifier for the scene")
    description: str = Field(..., description="Detailed scene description with action and dialogue")
    assets: List[AssetLite] = Field(..., description="Exactly 2 assets: one image and one video")


class EpisodeLite(BaseModel):
    """Simplified episode schema for LLM generation"""
    id: str = Field(..., description="Unique identifier for the episode")
    title: str = Field(..., description="Episode title")
    description: str = Field(..., description="Episode description")
    scenes: List[SceneLite] = Field(..., description="Episode scenes (3-5 scenes)")


class CharacterLite(BaseModel):
    """Simplified character schema for LLM generation"""
    id: str = Field(..., description="Unique identifier for the character")
    name: str = Field(..., description="Character name")
    description: str = Field(..., description="Character description with personality and background")
    gender: str = Field(..., description="Character gender (male/female/other)")
    main: bool = Field(..., description="Whether this is a main character (1-2 main characters)")
    premise_url: Optional[str] = Field(None, description="URL to character premise image if provided in premise")


class DramaLite(BaseModel):
    """Simplified drama schema for LLM generation (only required fields)"""
    title: str = Field(..., description="Title of the drama")
    description: str = Field(..., description="Brief description of the drama")
    characters: List[CharacterLite] = Field(..., description="Drama characters (1-2 main, 4-6 total)")
    episodes: List[EpisodeLite] = Field(..., description="Drama episodes (2-3 episodes)")
