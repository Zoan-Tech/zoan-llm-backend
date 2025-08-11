"""
Example usage of the exception handling decorators from utils.exception_handler

This file demonstrates how to use the various decorators across different scenarios.
"""

from utils.exception_handler import (
    exception_handler,
    graph_builder_exception_handler,
    safe_operation,
    validation_handler,
    api_operation_handler,
    GraphBuilderError,
    APIError
)
import logging

logger = logging.getLogger(__name__)


class ExampleService:
    """Example service showing decorator usage patterns."""
    
    @graph_builder_exception_handler("Failed to process data")
    def process_critical_data(self, data):
        """Critical operation that must not fail silently."""
        if not data:
            raise ValueError("Data cannot be empty")
        
        # Process data...
        return {"processed": True, "data": data}
    
    @safe_operation(default_return=[], log_level="warning")
    def get_optional_features(self):
        """Operation that can fail without breaking the main flow."""
        # This might call an external service that could be down
        raise ConnectionError("External service unavailable")
        # Will return [] instead of crashing
    
    @validation_handler("User input validation failed")
    def validate_user_input(self, user_data):
        """Validate user input with specific error handling."""
        if not isinstance(user_data, dict):
            raise ValueError("User data must be a dictionary")
        
        required_fields = ["name", "email"]
        for field in required_fields:
            if field not in user_data:
                raise ValueError(f"Missing required field: {field}")
    
    @api_operation_handler("External API call failed")
    def call_external_api(self, endpoint, payload):
        """Call to external API with proper error handling."""
        # Simulate API call
        if endpoint == "bad-endpoint":
            raise ConnectionError("Cannot connect to endpoint")
        
        return {"status": "success", "data": payload}
    
    @exception_handler(
        custom_exception=APIError,
        log_error=True,
        reraise=False,
        default_return={"error": "Service unavailable"},
        error_message_prefix="Service operation failed"
    )
    def custom_service_operation(self, param):
        """Example of using the generic exception handler with custom settings."""
        if param == "fail":
            raise RuntimeError("Simulated failure")
        
        return {"result": f"Processed {param}"}
    
    # Example of chaining decorators
    @safe_operation(default_return=None)
    @validation_handler("Complex operation validation failed")
    def complex_operation(self, config):
        """Complex operation with multiple layers of error handling."""
        # First validate
        if not config or not isinstance(config, dict):
            raise ValueError("Invalid configuration")
        
        # Then process (this could fail safely)
        result = self.process_critical_data(config.get("data"))
        
        return result


# Usage examples
def demonstrate_usage():
    """Demonstrate how the decorators work."""
    service = ExampleService()
    
    # This will work normally
    try:
        result = service.process_critical_data({"test": "data"})
        print(f"Success: {result}")
    except GraphBuilderError as e:
        print(f"Caught expected error: {e}")
    
    # This will return default value instead of failing
    features = service.get_optional_features()
    print(f"Optional features: {features}")  # Will print []
    
    # This will validate input
    try:
        service.validate_user_input({"name": "John", "email": "john@example.com"})
        print("Validation passed")
    except Exception as e:
        print(f"Validation failed: {e}")
    
    # This will not crash the application
    result = service.custom_service_operation("fail")
    print(f"Service result: {result}")  # Will print {"error": "Service unavailable"}


if __name__ == "__main__":
    demonstrate_usage()
