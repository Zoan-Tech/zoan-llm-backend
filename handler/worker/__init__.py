"""Worker manager for coordinating background workers."""

import asyncio
import threading
from typing import Dict, List, Optional

from config.logging import get_logger
from action.worker.base import BaseWorker
from action.worker.agent_reply import AgentReplyWorker

logger = get_logger()


class WorkerManager:
    """
    Manager for coordinating multiple background workers.
    
    This manager:
    - Initializes and registers workers automatically
    - Starts all workers in a single asyncio loop
    - Handles graceful shutdown of all workers
    - Provides a unified interface for worker lifecycle management
    """
    
    def __init__(self, asyncio_loop: Optional[asyncio.AbstractEventLoop] = None):
        """
        Initialize the worker manager.
        
        Args:
            asyncio_loop: Event loop for async operations
        """
        self.asyncio_loop = asyncio_loop
        self.workers: Dict[str, BaseWorker] = {}
        self._tasks: List[asyncio.Task] = []
        self._running = False
        
        # Auto-initialize workers
        self._init_workers()
    
    def _init_workers(self) -> None:
        """Initialize all workers."""
        # Initialize Agent Reply worker
        agent_reply_worker = AgentReplyWorker(
            poll_interval=1.0,
            batch_size=10,
            processing_timeout=300,
            asyncio_loop=self.asyncio_loop,
        )
        self.register_worker(agent_reply_worker)
        
        # TODO: Initialize other workers here
        # example_worker = ExampleWorker(asyncio_loop=self.asyncio_loop)
        # self.register_worker(example_worker)
    
    def register_worker(self, worker: BaseWorker) -> None:
        """
        Register a worker with the manager.
        
        Args:
            worker: Worker instance to register
        """
        if worker.name in self.workers:
            logger.warning(f"Worker '{worker.name}' already registered, replacing")
        
        self.workers[worker.name] = worker
    
    def unregister_worker(self, name: str) -> None:
        """
        Unregister a worker from the manager.
        
        Args:
            name: Worker name to unregister
        """
        if name in self.workers:
            del self.workers[name]
            logger.info(f"Unregistered worker: {name}")
        else:
            logger.warning(f"Worker '{name}' not found for unregistration")
    
    def get_worker(self, name: str) -> Optional[BaseWorker]:
        """
        Get a registered worker by name.
        
        Args:
            name: Worker name
        
        Returns:
            Worker instance or None if not found
        """
        return self.workers.get(name)
    
    async def start_all(self) -> None:
        """Start all registered workers."""
        if not self.workers:
            logger.warning("No workers registered to start")
            return
        
        self._running = True
        
        # Create tasks for all workers
        for worker in self.workers.values():
            task = asyncio.create_task(worker.start())
            self._tasks.append(task)
            logger.info(f"Started worker: {worker.name}")
        
        # Wait for all tasks to complete (or until stopped)
        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"Error in worker manager: {e}")
    
    def stop_all(self) -> None:
        """Stop all running workers."""
        if not self.workers:
            return
        
        logger.info(f"Stopping {len(self.workers)} worker(s)")
        self._running = False
        
        for worker in self.workers.values():
            try:
                worker.stop()
                logger.info(f"Stopped worker: {worker.name}")
            except Exception as e:
                logger.error(f"Error stopping worker '{worker.name}': {e}")
        
        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        self._tasks.clear()
    
    def is_running(self) -> bool:
        """Check if manager is running."""
        return self._running
    
    def get_worker_status(self) -> Dict[str, bool]:
        """
        Get status of all workers.
        
        Returns:
            Dictionary mapping worker names to running status
        """
        return {name: worker.is_running() for name, worker in self.workers.items()}
    
    def list_workers(self) -> List[str]:
        """
        List all registered worker names.
        
        Returns:
            List of worker names
        """
        return list(self.workers.keys())


__all__ = ["WorkerManager"]
