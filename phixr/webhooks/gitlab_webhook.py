"""GitLab webhook handlers."""
import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from phixr.config import settings
from phixr.handlers import CommentHandler

logger = logging.getLogger(__name__)


class WebhookValidator:
    """Validates GitLab webhook signatures."""
    
    @staticmethod
    def validate_signature(payload_body: bytes, signature: str, secret: str) -> bool:
        """Validate webhook signature.
        
        Args:
            payload_body: Raw webhook payload
            signature: X-Gitlab-Token header value
            secret: Webhook secret
            
        Returns:
            True if signature is valid, False otherwise
        """
        expected_signature = hmac.new(
            secret.encode(),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)


def setup_webhook_routes(comment_handler: CommentHandler):
    """Setup webhook routes with comment handler.

    Args:
        comment_handler: CommentHandler instance
    """
    router = APIRouter(prefix="/webhooks", tags=["webhooks"])

    @router.post("/gitlab")
    async def handle_gitlab_webhook(request: Request):
        """Handle incoming GitLab webhook events."""

        # Get webhook secret from header
        webhook_token = request.headers.get("X-Gitlab-Token", "")

        if not webhook_token == settings.webhook_secret:
            logger.warning("Invalid webhook signature")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid webhook signature"}
            )

        # Get webhook data
        try:
            webhook_data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse webhook JSON: {e}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid JSON payload"}
            )

        event_type = webhook_data.get("object_kind")

        logger.info(f"Received webhook event: {event_type}")
        logger.debug(f"Full webhook payload: {webhook_data}")

        # Handle issue comment events
        if event_type == "note":
            noteable_type = webhook_data.get("object_attributes", {}).get("noteable_type")

            if noteable_type == "Issue":
                logger.info("Processing Issue comment")
                success = await comment_handler.handle_issue_comment(webhook_data)
                logger.info(f"Comment handler returned: {success}")

                if success:
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content={"status": "processed"}
                    )
                else:
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content={"status": "ignored"}
                    )

            # Other events are ignored
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"status": "ignored"}
            )

    return router
