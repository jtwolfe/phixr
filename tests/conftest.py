"""Pytest configuration and fixtures."""

import pytest
import os
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables to prevent loading from .env.local."""
    with patch.dict(os.environ, {
        'PHIXR_SANDBOX_DOCKER_HOST': 'unix:///var/run/docker.sock',
        'PHIXR_SANDBOX_OPENCODE_IMAGE': 'ghcr.io/phixr/opencode:latest',
        'PHIXR_SANDBOX_DOCKER_NETWORK': 'phixr-network',
    }, clear=False):
        yield


def pytest_configure(config):
    """Configure pytest."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test (no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test (requires Docker)"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
