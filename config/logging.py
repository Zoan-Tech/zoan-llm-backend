import os
import logging
import logging.config
from uvicorn.config import LOGGING_CONFIG
from utils.enums import SecretEnum

def setup_logging():
	"""
	Setup logging configuration for the application.
	"""
	logging_config = LOGGING_CONFIG.copy()
	logging.config.dictConfig(logging_config)

def get_logger() -> logging.Logger:
	"""
	Get the application logger.
	"""
	LOGGING_CONFIG["loggers"]["uvicorn"]["level"] = os.getenv(SecretEnum.LOG_LEVEL.value, "INFO")
	return logging.getLogger("uvicorn")