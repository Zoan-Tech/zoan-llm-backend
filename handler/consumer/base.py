from typing import Dict
from abc import ABC, abstractmethod

class BaseMessageHandler(ABC):
    """Abstract base class for message handlers"""
    
    @abstractmethod
    async def handle(self, key: str, value: str, headers: Dict, meta: Dict) -> bool:
        """Handle the message and return success status"""
        pass