"""API client utilities for Drama viewer"""
import requests
from typing import Optional, Dict, Any, List
import os


class DramaAPIClient:
    """Client for interacting with the Drama Generation API"""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["X-API-Key"] = api_key

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("headers", {}).update(self.headers)

        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")

    def get_drama(self, drama_id: str) -> Dict[str, Any]:
        """Get drama by ID"""
        return self._make_request("GET", f"/dramas/{drama_id}")

    def list_dramas(self, skip: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """List all dramas with pagination"""
        return self._make_request("GET", f"/dramas?skip={skip}&limit={limit}")

    def get_job(self, drama_id: str, job_id: str) -> Dict[str, Any]:
        """Get job status"""
        return self._make_request("GET", f"/dramas/{drama_id}/jobs/{job_id}")

    def list_jobs(self, drama_id: str) -> List[Dict[str, Any]]:
        """List all jobs for a drama"""
        return self._make_request("GET", f"/dramas/{drama_id}/jobs")

    def delete_drama(self, drama_id: str) -> Dict[str, Any]:
        """Delete drama"""
        return self._make_request("DELETE", f"/dramas/{drama_id}")

    def improve_drama(self, drama_id: str, feedback: str) -> Dict[str, Any]:
        """Improve drama with feedback"""
        return self._make_request("POST", f"/dramas/{drama_id}/improve",
                                 json={"feedback": feedback})

    def critique_drama(self, drama_id: str) -> Dict[str, Any]:
        """Get AI critique of drama"""
        return self._make_request("POST", f"/dramas/{drama_id}/critique")

    def generate_full_drama(self, drama_id: str) -> Dict[str, Any]:
        """Trigger full drama DAG generation"""
        return self._make_request("POST", f"/dramas/{drama_id}/generate")

    def generate_character(self, drama_id: str, character_id: str) -> Dict[str, Any]:
        """Generate single character portrait"""
        return self._make_request("POST", f"/dramas/{drama_id}/characters/{character_id}/generate")

    def list_assets(self, user_id: str = "10000", project_name: Optional[str] = None,
                   asset_type: Optional[str] = None, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """List assets from asset library"""
        params = {"user_id": user_id}
        if project_name:
            params["project_name"] = project_name
        if asset_type:
            params["asset_type"] = asset_type
        if tag:
            params["tag"] = tag

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return self._make_request("GET", f"/asset-library/list?{query_string}")


def get_client() -> DramaAPIClient:
    """Get configured API client"""
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    api_key = os.getenv("API_KEY", None)
    return DramaAPIClient(base_url=base_url, api_key=api_key)
