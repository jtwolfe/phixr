"""Bridge package — OpenCode HTTP client."""

from .opencode_client import OpenCodeServerClient, OpenCodeServerError

__all__ = ["OpenCodeServerClient", "OpenCodeServerError"]
