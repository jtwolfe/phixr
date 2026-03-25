"""Webhook event handlers."""
import logging
from typing import Optional
from phixr.config import settings
from phixr.utils import GitLabClient
from phixr.commands import CommandParser
from phixr.context import ContextExtractor

logger = logging.getLogger(__name__)


class AssignmentHandler:
    """Handles issue assignment tracking."""
    
    def __init__(self, bot_user_id: int):
        """Initialize assignment handler.
        
        Args:
            bot_user_id: ID of the bot user
        """
        self.bot_user_id = bot_user_id
        # In a real implementation, this would be backed by Redis/DB
        self.assigned_issues = set()
    
    def track_assignment(self, project_id: int, issue_id: int, assignee_ids: list):
        """Track if the bot is assigned to an issue.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            assignee_ids: List of user IDs assigned to the issue
        """
        issue_key = f"{project_id}:{issue_id}"
        
        if self.bot_user_id in assignee_ids:
            self.assigned_issues.add(issue_key)
            logger.info(f"Bot assigned to issue {issue_key}")
        else:
            self.assigned_issues.discard(issue_key)
            logger.info(f"Bot unassigned from issue {issue_key}")
    
    def is_bot_assigned(self, project_id: int, issue_id: int) -> bool:
        """Check if bot is assigned to an issue.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            
        Returns:
            True if bot is assigned, False otherwise
        """
        issue_key = f"{project_id}:{issue_id}"
        return issue_key in self.assigned_issues
    
    def get_assigned_issues(self) -> set:
        """Get all issues the bot is assigned to.
        
        Returns:
            Set of issue keys (format: "project_id:issue_id")
        """
        return self.assigned_issues.copy()


class CommentHandler:
    """Handles issue comment events from webhooks."""
    
    def __init__(self, gitlab_client: GitLabClient, bot_user_id: int,
                 assignment_handler: AssignmentHandler):
        """Initialize comment handler.
        
        Args:
            gitlab_client: GitLab API client
            bot_user_id: ID of the bot user
            assignment_handler: Assignment tracking handler
        """
        self.gitlab_client = gitlab_client
        self.bot_user_id = bot_user_id
        self.assignment_handler = assignment_handler
        self.context_extractor = ContextExtractor(gitlab_client)
        self.command_parser = CommandParser()
    
    def handle_issue_comment(self, webhook_data: dict) -> bool:
        """Handle an issue comment webhook event.
        
        Args:
            webhook_data: Webhook payload from GitLab
            
        Returns:
            True if handled successfully, False otherwise
        """
        try:
            # Extract relevant data from webhook
            action = webhook_data.get('action')
            project_id = webhook_data['project']['id']
            issue_id = webhook_data['object_attributes']['iid']
            comment_author = webhook_data['user']['username']
            comment_id = webhook_data['object_attributes']['id']
            comment_body = webhook_data['object_attributes']['note']
            
            logger.info(f"Received comment on issue {project_id}/{issue_id} from {comment_author}")
            
            # Check if bot is assigned to this issue
            if not self.assignment_handler.is_bot_assigned(project_id, issue_id):
                logger.debug(f"Bot not assigned to issue {project_id}/{issue_id}, ignoring")
                return False
            
            # Parse commands from comment
            commands = self.command_parser.extract_commands(comment_body)
            
            if not commands:
                logger.debug(f"No commands found in comment")
                return False
            
            # Process each command
            for command_name, args in commands:
                logger.info(f"Processing command: {command_name} with args {args}")
                self._process_command(command_name, args, project_id, issue_id,
                                    comment_author, comment_id, comment_body)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling comment event: {e}", exc_info=True)
            return False
    
    def _process_command(self, command_name: str, args: list,
                        project_id: int, issue_id: int, comment_author: str,
                        comment_id: int, comment_body: str):
        """Process a single command.
        
        Args:
            command_name: Name of the command
            args: Command arguments
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            comment_author: Author of the comment
            comment_id: ID of the comment
            comment_body: Full comment text
        """
        if command_name == 'ai-status':
            self._handle_status_command(project_id, issue_id)
        elif command_name == 'ai-help':
            self._handle_help_command(project_id, issue_id)
        elif command_name == 'ai-acknowledge':
            self._handle_acknowledge_command(project_id, issue_id)
        else:
            self._handle_future_command(command_name, project_id, issue_id)
    
    def _handle_status_command(self, project_id: int, issue_id: int):
        """Handle /ai-status command."""
        context = self.context_extractor.extract_issue_context(project_id, issue_id)
        
        if not context:
            response = "❌ Could not extract issue context"
        else:
            response = f"""
✅ Bot Status: Ready

**Issue Context:**
- Title: {context.title}
- Author: {context.author}
- Assignees: {', '.join(context.assignees) or 'None'}
- Labels: {', '.join(context.labels) or 'None'}
- Comments: {len(context.comments)}

Use `/ai-help` to see available commands.
            """.strip()
        
        self.gitlab_client.add_issue_comment(project_id, issue_id, response)
    
    def _handle_help_command(self, project_id: int, issue_id: int):
        """Handle /ai-help command."""
        available_commands = self.command_parser.get_supported_commands()
        
        response = "📚 **Available Commands:**\n\n"
        
        # Phase 1 commands
        phase_1 = self.command_parser.get_phase_1_commands()
        response += "**Phase 1 (Available Now):**\n"
        for cmd, desc in phase_1.items():
            response += f"- `/{cmd}` - {desc}\n"
        
        # Future commands
        future_cmds = {k: v for k, v in available_commands.items() if k not in phase_1}
        if future_cmds:
            response += "\n**Coming Soon:**\n"
            for cmd, desc in future_cmds.items():
                response += f"- `/{cmd}` - {desc}\n"
        
        self.gitlab_client.add_issue_comment(project_id, issue_id, response)
    
    def _handle_acknowledge_command(self, project_id: int, issue_id: int):
        """Handle /ai-acknowledge command."""
        response = "👋 **Phixr Bot:** I'm ready to assist with this issue! Use `/ai-help` for available commands."
        self.gitlab_client.add_issue_comment(project_id, issue_id, response)
    
    def _handle_future_command(self, command_name: str, project_id: int, issue_id: int):
        """Handle commands that are implemented in future phases."""
        response = f"⏳ Command `/{command_name}` is coming in a future phase. Stay tuned!"
        self.gitlab_client.add_issue_comment(project_id, issue_id, response)
