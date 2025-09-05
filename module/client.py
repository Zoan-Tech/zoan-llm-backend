import os
from typing import Optional
import httpx

from utils.enums import SecretEnum
from utils.client_handler import api_error_handler

class ModType:
    LLM_CALL = "llm_call"
    HUMAN_INPUT = "human_input"
    # Add other module types as needed

class ModName:
    CODE_GENERATION = "code_generation"
    # Add other module names as needed

mod_mapping = {
    ModName.CODE_GENERATION: "js-game-generator",
}

class ModuleClient:
    EXECUTE_MODULE_ENDPOINT = "admin/plugins/handle-request"
    """
    Client for interacting with the module server.

    This client is used to send requests to the module server for various operations.
    Attributes:
        api_key (Optional[str]): API key for authentication.
        host (Optional[str]): Host URL for the module server.
        client (Optional[httpx.AsyncClient]): HTTP client for making requests.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.MODULE_PREFIX = "builtin-"
        self.api_key = api_key or os.getenv(SecretEnum.MODULE_API_KEY.value)
        self.host = host or os.getenv(SecretEnum.MODULE_HOST.value)
        
        if not self.host:
            raise ValueError("Module host is not set. Please provide a valid host URL.")
        
        if not self.api_key:
            raise ValueError("Module API key is not set. Please provide a valid API key.")

        if client is not None:
            self.client = client
            self.client.base_url = httpx.URL(self.host)
            self.client.headers.update(
                {"Authorization": f"Bearer {self.api_key}"}
            )
        else:
            self.client = httpx.Client(
                base_url=self.host,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=httpx.Timeout(120.0, connect=5.0)
            )
    
    @api_error_handler
    def execute_module(
        self,
        module_name: str,
        payload: Optional[dict] = None,
    ) -> dict:
        """
        Execute a module with the given name and payload.

        Args:
            module_name (str): Name of the module to execute.
            payload (dict): Payload to send to the module.

        Returns:
            dict: Response from the module server.
        """
        url = f"{self.EXECUTE_MODULE_ENDPOINT}"
        module_name = self.MODULE_PREFIX + mod_mapping.get(module_name, module_name)
        json_body = {
            "module_name": module_name,
            "payload": payload or {},
        }

        response = self.client.post(
            url,
            json=json_body,
        )
        
        response.raise_for_status()
        return response.json()