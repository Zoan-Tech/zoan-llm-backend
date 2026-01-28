"""Base worker class for background processing."""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from config.logging import get_logger

logger = get_logger()


class BaseWorker(ABC):
    """
    Abstract base class for background workers.
    
    Workers poll for work and process items in the background.
    Subclasses must implement the process() method.
    """
    
    def __init__(
        self,
        name: str,
        poll_interval: float = 1.0,
        asyncio_loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        """
        Initialize the base worker.
        
        Args:
            name: Worker name for logging
            poll_interval: Seconds to wait between polling cycles
            asyncio_loop: Event loop for async operations
        """
        self.name = name
        self.poll_interval = poll_interval
        self.asyncio_loop = asyncio_loop
        self._running = False
        self._stop_event = asyncio.Event() if asyncio_loop else None
    
    @abstractmethod
    async def process(self) -> None:
        """
        Process work items. Must be implemented by subclasses.
        
        This method is called repeatedly in the worker loop.
        It should:
        1. Query for work items
        2. Process them
        3. Handle errors appropriately
        """
        pass
    
    async def start(self):
        """Start the worker loop."""
        self._running = True
        if self._stop_event:
            self._stop_event.clear()
        
        try:
            while self._running:
                try:
                    # Process work items
                    await self.process()
                    
                except Exception as e:
                    logger.exception(f"Error in {self.name} worker: {e}")
                
                # Wait before next poll
                if self._stop_event:
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(),
                            timeout=self.poll_interval
                        )
                        break  # Stop event was set
                    except asyncio.TimeoutError:
                        continue  # Normal timeout, continue polling
                else:
                    await asyncio.sleep(self.poll_interval)
        
        finally:
            logger.info(f"{self.name} worker stopped")
    
    def stop(self):
        """Stop the worker gracefully."""
        logger.info(f"Stopping {self.name} worker")
        self._running = False
        if self._stop_event:
            self._stop_event.set()
    
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
