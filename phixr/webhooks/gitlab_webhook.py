"""GitLab webhook handlers."""
import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from phixr.config import settings
from phixr.handlers import CommentHandler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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
    
    @router.post("/gitlab")
    async def handle_gitlab_webhook(request: Request):
        """Handle incoming GitLab webhook events."""
        
        # Get webhook secret from header
        webhook_token = request.headers.get("X-Gitlab-Token", "")
        
        # Validate signature
        if not webhook_token == settings.webhook_secret:
            logger.warning("Webhook signature validation failed")
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
                content={"error": "Invalid JSON"}
            )
        
        # Get event type
        event_type = webhook_data.get("object_kind")
        
        logger.info(f"Received webhook event: {event_type}")
        
        # Handle issue note (comment) event
        if event_type == "note":
            noteable_type = webhook_data.get("object_attributes", {}).get("noteable_type")
            
            if noteable_type == "Issue":
                success = comment_handler.handle_issue_comment(webhook_data)
                
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
        
        # Handle issue assignment changes
        elif event_type == "issue":
            action = webhook_data.get("action")
            
            if action in ["open", "update"]:
                try:
                    project_id = webhook_data["project"]["id"]
                    issue_id = webhook_data["object_attributes"]["iid"]
                    assignee_ids = [a["id"] for a in webhook_data["object_attributes"].get("assignees", [])]
                    
                    comment_handler.assignment_handler.track_assignment(
                        project_id, issue_id, assignee_ids
                    )
                    
                    logger.info(f"Updated assignment tracking for issue {project_id}/{issue_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to track assignment: {e}", exc_info=True)
            
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"status": "processed"}
            )
        
        # Other events are ignored
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ignored"}
        )
    
    return router
