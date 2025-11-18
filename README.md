# SFD Production Server

FastAPI-based Drama Generation API with GPT-5 integration, designed for deployment on Railway.

## Features

- **AI-Powered Drama Generation**: Generate complete short-form dramas from text prompts using GPT-5
- **Full CRUD Operations**: Manage dramas, characters, episodes, scenes, and assets
- **Async Job Processing**: Background task processing for long-running AI operations
- **R2 Storage Backend**: Cloudflare R2 for drama persistence
- **API Key Authentication**: Secure endpoints with API key validation
- **OpenAPI/Swagger Documentation**: Interactive API documentation at `/docs`

## Architecture

- **FastAPI Server**: High-performance async API framework
- **Background Tasks**: Async drama generation (30-60 seconds)
- **R2 Storage**: S3-compatible object storage for drama data
- **GPT-5 Integration**: OpenAI API for drama generation

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key with GPT-5 access
- Cloudflare R2 bucket (or S3-compatible storage)

### Local Development

1. **Clone the repository**
   ```bash
   cd sfd-production-server
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Run the server**
   ```bash
   python main.py
   # Or use uvicorn directly:
   uvicorn main:app --reload --port 8000
   ```

6. **Access the API**
   - API: http://localhost:8000
   - Swagger Docs: http://localhost:8000/docs
   - OpenAPI Schema: http://localhost:8000/openapi.json

## Environment Variables

Create a `.env` file with the following variables:

```bash
# Environment
ENVIRONMENT=production
PORT=8000

# OpenAI Configuration
OPENAI_API_KEY=sk-proj-...
GPT_MODEL=gpt-5
# Optional: Custom OpenAI API base URL
# OPENAI_API_BASE=https://api.openai.com/v1

# API Authentication
API_KEYS=key1,key2,key3  # Comma-separated list

# R2 Storage (Cloudflare)
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key
R2_BUCKET=sfd-production
```

## Railway Deployment

### One-Click Deploy

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

### Manual Deployment

1. **Install Railway CLI**
   ```bash
   npm i -g @railway/cli
   ```

2. **Login to Railway**
   ```bash
   railway login
   ```

3. **Initialize project**
   ```bash
   railway init
   ```

4. **Set environment variables**
   ```bash
   railway variables set OPENAI_API_KEY=sk-proj-...
   railway variables set GPT_MODEL=gpt-5
   railway variables set API_KEYS=your-api-key-1,your-api-key-2
   railway variables set R2_ACCOUNT_ID=your-account-id
   railway variables set R2_ACCESS_KEY_ID=your-access-key-id
   railway variables set R2_SECRET_ACCESS_KEY=your-secret-access-key
   railway variables set R2_BUCKET=sfd-production
   railway variables set ENVIRONMENT=production
   ```

5. **Deploy**
   ```bash
   railway up
   ```

6. **Get your deployment URL**
   ```bash
   railway domain
   ```

### Railway Configuration

The project includes:
- `railway.toml`: Railway build and deployment configuration
- `Procfile`: Process configuration for Railway
- `runtime.txt`: Python version specification
- `requirements.txt`: Python dependencies

## API Documentation

### Authentication

All endpoints except `/health` require authentication via the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" https://api.example.com/dramas
```

### Key Endpoints

#### Health Check
```bash
GET /health
# No authentication required
```

#### Create Drama (Async)
```bash
POST /dramas
Content-Type: application/json
X-API-Key: your-api-key

{
  "premise": "A software engineer discovers their code is sentient. Make it 2 episodes."
}

# Response: 202 Accepted
{
  "dramaId": "drama_xyz",
  "jobId": "job_abc",
  "status": "pending",
  "message": "Drama generation job queued..."
}
```

#### Check Job Status
```bash
GET /dramas/{dramaId}/jobs/{jobId}
X-API-Key: your-api-key

# Response:
{
  "jobId": "job_abc",
  "status": "completed",  # or "pending", "processing", "failed"
  "dramaId": "drama_xyz",
  "type": "generate_drama",
  "createdAt": 1234567890000,
  "completedAt": 1234567950000
}
```

#### Get Drama
```bash
GET /dramas/{dramaId}
X-API-Key: your-api-key
```

#### List Dramas
```bash
GET /dramas?limit=100&cursor=abc123
X-API-Key: your-api-key
```

#### Improve Drama
```bash
POST /dramas/{dramaId}/improve
Content-Type: application/json
X-API-Key: your-api-key

{
  "feedback": "Make the dialogue more emotional and add a plot twist"
}
```

### Interactive Documentation

Visit `/docs` on your deployed server for full interactive API documentation powered by Swagger UI.

## R2 Storage Setup

### Cloudflare R2

1. **Create R2 bucket**
   - Go to Cloudflare Dashboard → R2
   - Create new bucket: `sfd-production`

2. **Generate API credentials**
   - Navigate to R2 → Manage R2 API Tokens
   - Create new API token with read/write permissions
   - Copy Account ID, Access Key ID, and Secret Access Key

3. **Configure environment**
   - Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in `.env` or Railway

### Alternative: MinIO (Local Development)

For local testing without R2:

```bash
# Run MinIO with Docker
docker run -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# Configure .env
R2_ENDPOINT_URL=http://localhost:9000
R2_ACCESS_KEY_ID=minioadmin
R2_SECRET_ACCESS_KEY=minioadmin
```

## Project Structure

```
sfd-production-server/
├── main.py                 # FastAPI application entry point
├── app/
│   ├── __init__.py
│   ├── models.py          # Pydantic models
│   ├── dependencies.py    # API key authentication
│   ├── storage.py         # R2 storage integration
│   ├── ai_service.py      # GPT-5 drama generation
│   ├── job_manager.py     # Job status tracking
│   └── routers/           # API route handlers
│       ├── dramas.py      # Drama CRUD endpoints
│       ├── jobs.py        # Job status endpoints
│       ├── characters.py  # Character endpoints
│       ├── episodes.py    # Episode endpoints
│       ├── scenes.py      # Scene endpoints
│       └── assets.py      # Asset endpoints
├── requirements.txt       # Python dependencies
├── runtime.txt           # Python version
├── Procfile              # Railway process configuration
├── railway.toml          # Railway deployment config
├── .env.example          # Environment template
└── README.md             # This file
```

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Code Formatting

```bash
# Install formatting tools
pip install black isort

# Format code
black .
isort .
```

## API Features

### Drama Management
- ✅ Create dramas from text prompts (async with GPT-5)
- ✅ Create dramas from JSON (sync)
- ✅ List dramas with pagination
- ✅ Get drama by ID
- ✅ Update drama properties
- ✅ Delete dramas
- ✅ Improve dramas with feedback

### Job Tracking
- ✅ Check job status
- ✅ List all jobs for a drama
- ✅ Real-time status updates (pending → processing → completed/failed)

### Character Management
- ✅ List characters in a drama
- ✅ Get character by ID
- ✅ Update character properties

### Episode Management
- ✅ List episodes in a drama
- ✅ Get episode by ID
- ✅ Update episode properties

### Scene Management
- ✅ List scenes in an episode
- ✅ Get scene by ID
- ✅ Update scene properties

### Asset Management
- ✅ List assets in a scene
- ✅ Get asset by ID
- ✅ Update asset properties

## Troubleshooting

### R2 Connection Issues

```python
# Test R2 connection
from app.storage import storage
import asyncio

async def test():
    dramas, cursor = await storage.list_dramas(limit=1)
    print(f"Found {len(dramas)} dramas")

asyncio.run(test())
```

### OpenAI API Issues

Check your API key and model access:
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | grep gpt-5
```

### Railway Logs

```bash
railway logs
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/SFD-Hackathon/drama-api-worker/issues
- Documentation: https://api.shortformdramas.com/docs
