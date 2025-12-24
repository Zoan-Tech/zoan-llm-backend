import httpx
from typing import Optional
from external.app_preview.model import (
    BuildRequest,
    BuildResponse,
    LogsResponse,
)

from config import Config

class RoutePrefix(str):
    BUILD: str = "/build"
    LOGS: str = "/logs"

class Service:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or Config.APP_PREVIEW_URL

    def build_app_preview(self, request: BuildRequest, extra_headers: dict = {}) -> Optional[BuildResponse]:
        url = f"{self.base_url}{RoutePrefix.BUILD}"
        
        response = httpx.post(url, json=request.model_dump(), headers=extra_headers)
        response.raise_for_status()
        
        response_data = response.json()
        if response_data:
            return BuildResponse.model_validate(response_data)
        return None
    
    def get_build_status(self, build_id: str, extra_headers: dict = {}) -> Optional[BuildResponse]:
        url = f"{self.base_url}{RoutePrefix.BUILD}/{build_id}/status"
        
        response = httpx.get(url, headers=extra_headers)
        response.raise_for_status()
        
        response_data = response.json()
        if response_data:
            return BuildResponse.model_validate(response_data)
        return None
    
    def get_build_logs(self, build_id: str, tail: int = 100, follow: bool = False, timestamps: bool = True, extra_headers: dict = {}) -> Optional[LogsResponse]:
        url = f"{self.base_url}{RoutePrefix.LOGS}/{build_id}"
        params = {
            "tail": tail,
            "follow": str(follow).lower(),
            "timestamps": str(timestamps).lower(),
        }
        
        response = httpx.get(url, params=params, headers=extra_headers)
        response.raise_for_status()
        
        response_data = response.json()
        if response_data:
            return LogsResponse.model_validate(response_data)
        return None
    
service = Service()