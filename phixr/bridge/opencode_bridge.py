"""OpenCode bridge for context-to-container communication."""
import logging

logger = logging.getLogger(__name__)


class OpenCodeBridge:
    """Bridge for passing context to OpenCode container.
    
    In Phase 1d, this is a placeholder design for Phase 2.
    Will manage OpenCode container lifecycle and context passing.
    """
    
    def __init__(self):
        """Initialize OpenCode bridge."""
        pass
    
    def start_opencode_session(self, context, execution_mode='env'):
        """Start an OpenCode container session.
        
        Args:
            context: IssueContext object
            execution_mode: How to pass context ('env', 'api', or 'file')
            
        Returns:
            Session info or None if failed
        """
        # TODO: Implement in Phase 2
        logger.info(f"OpenCode bridge: start_opencode_session (placeholder, mode={execution_mode})")
        return None
    
    def stop_opencode_session(self, session_id):
        """Stop an OpenCode container session.
        
        Args:
            session_id: ID of the session to stop
            
        Returns:
            True if successful, False otherwise
        """
        # TODO: Implement in Phase 2
        logger.info("OpenCode bridge: stop_opencode_session (placeholder)")
        return True
