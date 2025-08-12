import logging
from functools import wraps
from typing import Type, Union, Callable, Any, Optional
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class GraphBuilderError(Exception):
    """Custom exception for GraphBuilder errors."""
    pass


class PromptNotFoundError(GraphBuilderError):
    """Exception raised when a prompt is not found in Langfuse."""
    pass


class AgentConfigurationError(GraphBuilderError):
    """Exception raised for agent configuration errors."""
    pass


class APIError(Exception):
    """Exception raised for errors in the API."""
    pass


def exception_handler(
    custom_exception: Type[Exception] = None,
    log_error: bool = True,
    reraise: bool = True,
    default_return: Any = None,
    error_message_prefix: str = "",
    handle_specific: dict = None
):
    """
    A comprehensive exception handling decorator.
    
    Args:
        custom_exception: Custom exception to raise instead of original
        log_error: Whether to log the error
        reraise: Whether to reraise the exception (False means return default_return)
        default_return: Value to return if reraise=False
        error_message_prefix: Prefix to add to error messages
        handle_specific: Dict mapping exception types to custom handlers
    
    Usage:
        @exception_handler(custom_exception=GraphBuilderError, error_message_prefix="Failed to build agent")
        def build_agent(self, config):
            # function implementation
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get function context for better logging
                func_name = func.__name__
                class_name = ""
                if args and hasattr(args[0], '__class__'):
                    class_name = args[0].__class__.__name__
                context = f"{class_name}.{func_name}" if class_name else func_name
                
                # Handle specific exceptions differently if configured
                if handle_specific and type(e) in handle_specific:
                    handler = handle_specific[type(e)]
                    if callable(handler):
                        return handler(e, *args, **kwargs)
                    else:
                        # Handler is a return value
                        if log_error:
                            logger.error(f"Handled specific exception in {context}: {e}")
                        return handler
                
                # Determine error message
                error_msg = f"{error_message_prefix}: {str(e)}" if error_message_prefix else str(e)
                
                # Log the error if requested
                if log_error:
                    logger.error(f"Exception in {context}: {error_msg}")
                    logger.debug(f"Exception details", exc_info=True)
                
                # Handle different exception types
                if isinstance(e, ValidationError):
                    error_msg = f"Validation error in {context}: {e}"
                elif isinstance(e, (ConnectionError, TimeoutError)):
                    error_msg = f"Network error in {context}: {e}"
                elif isinstance(e, ValueError):
                    error_msg = f"Value error in {context}: {e}"
                
                # Decide whether to reraise or return default
                if reraise:
                    if custom_exception:
                        import traceback
                        traceback.print_exc()  # Log the traceback for debugging
                        raise custom_exception(error_msg) from e
                    else:
                        raise
                else:
                    logger.warning(f"Returning default value {default_return} due to exception in {context}")
                    return default_return
                    
        return wrapper
    return decorator


def graph_builder_exception_handler(error_message_prefix: str = ""):
    """
    Specialized exception handler for GraphBuilder methods.
    
    Usage:
        @graph_builder_exception_handler("Failed to build agent")
        def build_agent(self, config):
            # function implementation
    """
    return exception_handler(
        custom_exception=GraphBuilderError,
        log_error=True,
        reraise=True,
        error_message_prefix=error_message_prefix,
        handle_specific={
            ValidationError: lambda e, *args, **kwargs: AgentConfigurationError(f"Invalid configuration: {e}"),
            PromptNotFoundError: lambda e, *args, **kwargs: e,  # Re-raise as-is
            APIError: lambda e, *args, **kwargs: GraphBuilderError(f"API operation failed: {e}")
        }
    )


def safe_operation(default_return: Any = None, log_level: str = "warning"):
    """
    Exception handler for operations that should not fail the entire process.
    
    Usage:
        @safe_operation(default_return=[], log_level="error")
        def get_optional_data(self):
            # This won't crash the app if it fails
    """
    def log_func(msg):
        getattr(logger, log_level.lower(), logger.warning)(msg)
    
    return exception_handler(
        custom_exception=None,
        log_error=True,
        reraise=False,
        default_return=default_return,
        handle_specific={
            Exception: lambda e, *args, **kwargs: (log_func(f"Safe operation failed, returning default: {e}"), default_return)[1]
        }
    )


def validation_handler(error_message_prefix: str = "Validation failed"):
    """
    Specialized handler for validation operations.
    
    Usage:
        @validation_handler("Agent config validation failed")
        def validate_config(self, config):
            # validation logic
    """
    return exception_handler(
        custom_exception=AgentConfigurationError,
        log_error=True,
        reraise=True,
        error_message_prefix=error_message_prefix,
        handle_specific={
            ValidationError: lambda e, *args, **kwargs: AgentConfigurationError(f"Pydantic validation error: {e}"),
            ValueError: lambda e, *args, **kwargs: AgentConfigurationError(f"Value validation error: {e}")
        }
    )


def api_operation_handler(error_message_prefix: str = "API operation failed"):
    """
    Specialized handler for API operations.
    
    Usage:
        @api_operation_handler("Module execution failed")
        def execute_module(self, name, payload):
            # API call logic
    """
    return exception_handler(
        custom_exception=APIError,
        log_error=True,
        reraise=True,
        error_message_prefix=error_message_prefix,
        handle_specific={
            ConnectionError: lambda e, *args, **kwargs: APIError(f"Connection error: {e}"),
            TimeoutError: lambda e, *args, **kwargs: APIError(f"Timeout error: {e}"),
        }
    )
