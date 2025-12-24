"""gRPC server management module."""

import grpc
from concurrent import futures
from typing import Optional

from config import Config
from config.logging import get_logger
from handler.grpc.completion import CompletionServiceServicer
from handler.grpc.grpc_generated.completion import completion_pb2_grpc

logger = get_logger()


class GRPCServerManager:
    """Manages the lifecycle of the gRPC server."""
    
    def __init__(self):
        self._server: Optional[grpc.Server] = None
        self._listen_addr = f'[::]:{Config.GRPC_PORT}'
    
    def start(self) -> None:
        """Start the gRPC server."""
        if self._server is not None:
            logger.warning("gRPC server is already running")
            return
        
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=Config.MAX_WORKERS))
        completion_pb2_grpc.add_CompletionServiceServicer_to_server(  # type: ignore
            CompletionServiceServicer(), self._server
        )
        
        self._server.add_insecure_port(self._listen_addr)
        self._server.start()
        logger.info(f"gRPC server started on {self._listen_addr}")
    
    def wait_for_termination(self) -> None:
        """Block until the server terminates."""
        if self._server is None:
            logger.warning("gRPC server is not running")
            return
        
        try:
            self._server.wait_for_termination()
        except KeyboardInterrupt:
            logger.info("gRPC server shutdown requested")
    
    def stop(self, grace: float = 5.0) -> None:
        """Stop the gRPC server with a grace period."""
        if self._server is None:
            logger.warning("gRPC server is not running")
            return
        
        self._server.stop(grace=grace)
        self._server = None
        logger.info("gRPC server stopped")
    
    def run(self) -> None:
        """Start the server and wait for termination."""
        self.start()
        self.wait_for_termination()
