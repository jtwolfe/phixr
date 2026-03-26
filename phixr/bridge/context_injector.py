"""Context injection and serialization for OpenCode sessions.

For API-based sessions, context is injected via initial messages rather than
file volumes. This module provides utilities for preparing context for injection.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional

from phixr.models.issue_context import IssueContext
from phixr.models.execution_models import ExecutionConfig, ExecutionMode
from phixr.config.sandbox_config import SandboxConfig

logger = logging.getLogger(__name__)


class ContextInjector:
    """Prepares and injects Phixr issue context into OpenCode sessions.
    
    With API-based sessions, context is passed via the initial message
    rather than as mounted volumes.
    """
    
    def __init__(self, config: SandboxConfig):
        """Initialize context injector."""
        self.config = config
    
    def build_context_message(self, context: IssueContext, 
                             execution_config: ExecutionConfig) -> str:
        """Build the context message to inject into OpenCode session.
        
        This message will be sent as the first user message to OpenCode,
        providing all necessary context for the task.
        
        Args:
            context: Issue context from GitLab/GitHub
            execution_config: Execution configuration
            
        Returns:
            Formatted context message string
        """
        mode_str = "analysis and exploration (read-only)" if execution_config.mode == ExecutionMode.PLAN else "development"
        
        message = f"""# Phixr OpenCode Session

## Issue
**ID:** {context.issue_id}
**Title:** {context.title}

### Description
{context.description}

### Labels
{', '.join(context.labels) if context.labels else '(none)'}

## Your Task
You are in **{mode_str}** mode.

### Context
- **Repository:** {context.repo_url}
- **Branch:** {execution_config.branch}
- **Timeout:** {execution_config.timeout_minutes} minutes
- **Model:** {execution_config.model}

### Important Notes
1. All work should be done in the `{execution_config.branch}` branch
2. Commit your changes with clear, atomic commits
3. Use git diff to prepare your work for review
4. Follow the repository's coding standards and patterns
5. Add tests for new functionality

### Repository Structure
{self._format_repo_structure(context)}

---
Generated at {datetime.utcnow().isoformat()}Z by Phixr
"""
        return message
    
    def _format_repo_structure(self, context: IssueContext) -> str:
        """Format repository structure for display.
        
        Args:
            context: Issue context
            
        Returns:
            Formatted structure string
        """
        if not context.structure:
            return "Structure not available"
        
        if isinstance(context.structure, dict):
            lines = []
            for path, description in context.structure.items():
                lines.append(f"- **{path}**: {description}")
            return "\n".join(lines)
        
        return str(context.structure)
    
    def build_system_prompt(self, execution_config: ExecutionConfig) -> str:
        """Build system prompt for OpenCode agent.
        
        Args:
            execution_config: Execution configuration
            
        Returns:
            System prompt string
        """
        mode_instructions = {
            ExecutionMode.PLAN: """You are in READ-ONLY PLAN mode. You should:
1. Analyze the repository and issue thoroughly
2. Identify the files and components that need changes
3. Create a detailed plan for solving the issue
4. Do NOT make any actual code changes
5. Use 'git diff' to show what changes would be needed
6. Prepare a clear summary of your analysis""",
            ExecutionMode.BUILD: """You are in DEVELOPMENT mode. You should:
1. Analyze the repository and understand the issue
2. Make necessary code changes to fix the issue
3. Commit changes with clear commit messages
4. Add tests for new functionality
5. Use 'git diff' to verify your changes
6. Provide a summary of what was implemented""",
            ExecutionMode.REVIEW: """You are in REVIEW mode. You should:
1. Review the existing code and changes
2. Provide feedback and suggestions
3. Identify potential issues or improvements
4. Do NOT make changes to the codebase
5. Use code analysis and best practices
6. Provide a detailed review summary""",
        }
        
        instructions = mode_instructions.get(execution_config.mode, "")
        
        return f"""You are an expert software engineer working with the OpenCode agent framework.

Your task is to help solve a GitHub/GitLab issue by analyzing code and making necessary changes.

{instructions}

Always follow best practices and communicate your findings clearly."""
    
    def create_environment_variables(self, context: IssueContext,
                                    execution_config: ExecutionConfig,
                                    git_token: str) -> Dict[str, str]:
        """Create environment variables for OpenCode session.
        
        Note: With API-based sessions, we pass env vars via the OpenCode API
        rather than Docker environment. These are primarily for context.
        
        Args:
            context: Issue context
            execution_config: Execution configuration
            git_token: Git provider token for cloning
            
        Returns:
            Dictionary of environment variables
        """
        env_vars = {
            # Session identification
            "PHIXR_SESSION_ID": execution_config.session_id,
            "PHIXR_ISSUE_ID": str(context.issue_id),
            
            # Repository details
            "PHIXR_REPO_URL": context.repo_url,
            "PHIXR_BRANCH": execution_config.branch,
            "PHIXR_GIT_TOKEN": git_token,
            
            # Execution configuration
            "PHIXR_TIMEOUT": str(execution_config.timeout_minutes * 60),
            "OPENCODE_MODE": execution_config.mode if isinstance(execution_config.mode, str) else execution_config.mode.value,
            "OPENCODE_MODEL": execution_config.model,
            "OPENCODE_TEMPERATURE": str(execution_config.temperature),
            
            # Container behavior
            "OPENCODE_TELEMETRY": "0",
            "OPENCODE_LOG_LEVEL": self.config.log_level,
        }
        
        # Add OpenCode Zen API key if configured
        if self.config.zen_api_key:
            env_vars["OPENCODE_ZEN_API_KEY"] = self.config.zen_api_key
            logger.info("OpenCode Zen API key configured for session")
        
        return env_vars
    
    def cleanup_all(self) -> None:
        """Clean up temporary resources (no-op for API-based sessions)."""
        pass


