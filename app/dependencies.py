"""Dependencies for FastAPI endpoints"""

from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import API_KEYS

security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
    Verify API key from Authorization header or X-API-Key header.

    For development without API keys, this will pass through.
    For production, set API_KEYS environment variable.
    """
    # If no API keys configured, allow all requests (development mode)
    if not API_KEYS:
        return "dev"

    # Check if credentials provided
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide via 'Authorization: Bearer <key>' header"
        )

    # Verify the API key
    if credentials.credentials not in API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return credentials.credentials

