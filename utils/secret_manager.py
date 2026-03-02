from cryptography.fernet import Fernet
from config import Config
from pydantic import SecretStr
import base64
import json
from typing import Any


class SecretManager:
    def __init__(self, fernet_key: str = None):
        """
        Initialize with Fernet key from env or parameter
        """
        self.fernet_key = fernet_key or Config.FERNET_SECRET
        if not self.fernet_key:
            raise ValueError("FERNET_KEY not provided")
        self.cipher = Fernet(self.fernet_key.encode())
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key (do once, store in K8s secret)"""
        return Fernet.generate_key().decode()
    
    def encrypt(self, data: SecretStr) -> str:
        """Encrypt string to encrypted string"""
        encrypted = self.cipher.encrypt(data.encode())
        return encrypted.decode()
    
    def decrypt(self, encrypted_data: str) -> Any:
        """Decrypt encrypted string to original string"""
        decrypted = self.cipher.decrypt(encrypted_data.encode())
        res = decrypted.decode()
        return res

    @staticmethod
    def encode_base64(data: dict) -> str:
        """Encode dict to base64 string"""
        json_str = json.dumps(data)
        return base64.b64encode(json_str.encode()).decode()
    
    @staticmethod
    def decode_base64(data: str) -> dict:
        """Decode base64 string to dict"""
        json_str = base64.b64decode(data.encode()).decode()
        return json.loads(json_str)
    
secret_manager = SecretManager()