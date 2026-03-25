"""Webhooks package."""
from .gitlab_webhook import setup_webhook_routes, WebhookValidator

__all__ = ["setup_webhook_routes", "WebhookValidator"]
