"""Command parser for slash commands in issue comments."""
import re
import logging
from typing import Optional, List
from datetime import datetime
from phixr.models import Command

logger = logging.getLogger(__name__)


class CommandParser:
    """Parser for slash commands in issue comments."""
    
    # Supported commands in Phase 1
    PHASE_1_COMMANDS = {
        'ai-status': 'Show bot status and context',
        'ai-help': 'List available commands',
        'ai-acknowledge': "Bot acknowledges it's ready",
    }
    
    # Placeholder for future commands
    FUTURE_COMMANDS = {
        'ai-plan': 'AI generates implementation plan',
        'ai-implement': 'AI implements the task',
        'ai-review-mr': 'AI reviews a merge request',
        'ai-fix-tests': 'AI fixes failing tests',
        'ai-abort': 'Abort current operation',
    }
    
    ALL_COMMANDS = {**PHASE_1_COMMANDS, **FUTURE_COMMANDS}
    
    @staticmethod
    def parse_command(text: str) -> Optional[tuple[str, List[str]]]:
        """Parse a slash command from text.
        
        Args:
            text: Raw comment text
            
        Returns:
            Tuple of (command_name, args) or None if no command found
        """
        # Look for /ai-* pattern
        match = re.search(r'/ai-(\S+)(?:\s+(.*))?', text)
        
        if match:
            command_name = f"ai-{match.group(1)}"
            args_str = match.group(2) or ""
            args = args_str.split() if args_str else []
            
            return command_name, args
        
        return None
    
    @classmethod
    def extract_commands(cls, text: str) -> List[Optional[tuple[str, List[str]]]]:
        """Extract all commands from text (in case multiple are present).
        
        Args:
            text: Raw comment text
            
        Returns:
            List of parsed commands
        """
        commands = []
        # Find all /ai-* patterns
        for match in re.finditer(r'/ai-(\S+)(?:\s+(.*))?', text):
            command_name = f"ai-{match.group(1)}"
            args_str = match.group(2) or ""
            args = args_str.split() if args_str else []
            commands.append((command_name, args))
        
        return commands
    
    @classmethod
    def create_command_object(cls, command_name: str, args: List[str],
                            raw_text: str, author: str, issue_id: int,
                            project_id: int, comment_id: int) -> Optional[Command]:
        """Create a Command object from parsed data.
        
        Args:
            command_name: Name of the command (e.g., 'ai-status')
            args: Command arguments
            raw_text: Raw comment text
            author: Username of comment author
            issue_id: GitLab issue ID
            project_id: GitLab project ID
            comment_id: GitLab comment/note ID
            
        Returns:
            Command object or None if command is not recognized
        """
        if command_name not in cls.ALL_COMMANDS:
            logger.warning(f"Unknown command: {command_name}")
            return None
        
        return Command(
            name=command_name,
            args=args,
            raw_text=raw_text,
            author=author,
            issue_id=issue_id,
            project_id=project_id,
            comment_id=comment_id,
            timestamp=datetime.utcnow()
        )
    
    @classmethod
    def get_supported_commands(cls) -> dict:
        """Get all supported commands (Phase 1 + Future).
        
        Returns:
            Dictionary of command_name -> description
        """
        return cls.ALL_COMMANDS
    
    @classmethod
    def get_phase_1_commands(cls) -> dict:
        """Get Phase 1 commands only.
        
        Returns:
            Dictionary of command_name -> description
        """
        return cls.PHASE_1_COMMANDS
    
    @classmethod
    def is_phase_1_command(cls, command_name: str) -> bool:
        """Check if command is available in Phase 1.
        
        Args:
            command_name: Name of command to check
            
        Returns:
            True if command is in Phase 1, False otherwise
        """
        return command_name in cls.PHASE_1_COMMANDS
