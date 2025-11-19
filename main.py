"""
Drama API Worker - FastAPI Implementation
AI-powered Drama Generation API with GPT-5 integration
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from strawberry.fastapi import GraphQLRouter

# Load environment variables
load_dotenv()

# Import routers
from app.routers import dramas, jobs, characters, episodes, scenes, assets, asset_library
from app.graphql_schema import schema

# Version
VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    print(f"🚀 Drama API Server v{VERSION} starting...")
    print(f"📦 R2 Bucket: {os.getenv('R2_BUCKET', 'sfd-production')}")
    print(f"🤖 GPT Model: {os.getenv('GPT_MODEL', 'gpt-5')}")
    yield
    # Shutdown
    print("👋 Drama API Server shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Drama API Worker",
    description="""
AI-powered Drama Generation API built with FastAPI and GPT-5 integration.

This API provides comprehensive management of short-form drama content including:
- Asynchronous drama generation from text prompts using GPT-5
- Full CRUD operations for dramas, characters, episodes, scenes, and assets
- Job status tracking for long-running AI generation tasks
- R2 storage backend for drama persistence

## Architecture
- **FastAPI Server**: Fast API responses, background task processing
- **Background Tasks**: AI processing (30-60s for drama generation)
- **R2 Storage**: Drama persistence

## Authentication
All endpoints except `/health` require authentication via the `X-API-Key` header.
    """,
    version=VERSION,
    contact={
        "name": "Drama API Support",
        "url": "https://github.com/SFD-Hackathon/drama-api-worker",
    },
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dramas.router, prefix="/dramas", tags=["Dramas"])
app.include_router(jobs.router, prefix="/dramas", tags=["Jobs"])
app.include_router(characters.router, prefix="/dramas", tags=["Characters"])
app.include_router(episodes.router, prefix="/dramas", tags=["Episodes"])
app.include_router(scenes.router, prefix="/dramas", tags=["Scenes"])
app.include_router(assets.router, prefix="/dramas", tags=["Assets"])
app.include_router(asset_library.router, prefix="/asset-library", tags=["Asset Library"])

# GraphQL endpoint
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql", tags=["GraphQL"])


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint

    Returns service health status and version information.
    This endpoint does not require authentication.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": VERSION,
    }


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - redirect to docs"""
    return {
        "message": "Drama API Worker",
        "version": VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT") != "production",
    )
