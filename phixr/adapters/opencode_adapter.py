"""OpenCode adapter for context passing."""
import logging

logger = logging.getLogger(__name__)


class OpenCodeAdapter:
    """Adapter for OpenCode integration.
    
    In Phase 1 & 1d, this is a placeholder for future implementation.
    Will handle context serialization and OpenCode container lifecycle.
    """
    
    def __init__(self):
        """Initialize OpenCode adapter."""
        pass
    
    def prepare_context(self, context):
        """Prepare context for OpenCode.
        
        Args:
            context: IssueContext object
            
        Returns:
            Formatted context for OpenCode
        """
        # TODO: Implement in Phase 1d
        logger.info("OpenCode adapter: prepare_context (placeholder)")
        return None
    
    def trigger_opencode(self, context):
        """Trigger OpenCode with issue context.
        
        Args:
            context: IssueContext object
            
        Returns:
            Session ID or None if failed
        """
        # TODO: Implement in Phase 2
        logger.info("OpenCode adapter: trigger_opencode (placeholder)")
        return None
