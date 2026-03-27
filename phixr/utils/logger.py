"""Logging setup."""
import logging
import sys


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Set up a logger with console output.
    
    Args:
        name: Logger name
        level: Logging level (default INFO)
        
    Returns:
        Configured logger
    """
    # Configure root logger first
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler for root logger
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Get and return the logger for the specific module
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    return logger
