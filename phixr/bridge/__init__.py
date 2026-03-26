"""Bridge package."""

# Lazy import to avoid circular dependencies
def __getattr__(name):
    if name == "OpenCodeBridge":
        from .opencode_bridge import OpenCodeBridge
        return OpenCodeBridge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["OpenCodeBridge"]
