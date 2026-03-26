"""OpenCode Integration Service.

Provides clean, async integration with OpenCode for both API and UI embedding modes.
Replaces the problematic OpenCodeBridge with a proper service architecture.
"""

from .opencode_integration_service import OpenCodeIntegrationService, IntegrationMode

__all__ = ["OpenCodeIntegrationService", "IntegrationMode"]