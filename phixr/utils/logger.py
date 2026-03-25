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
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger
