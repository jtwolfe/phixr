"""Context injection and serialization for OpenCode containers."""

import json
import tempfile
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

from phixr.models.issue_context import IssueContext
from phixr.models.execution_models import ExecutionConfig, ExecutionMode
from phixr.config.sandbox_config import SandboxConfig

logger = logging.getLogger(__name__)


class ContextInjector:
    """Injects Phixr issue context into OpenCode containers."""
    
    def __init__(self, config: SandboxConfig):
        """Initialize context injector."""
        self.config = config
        self.temp_dirs: Dict[str, Path] = {}
    
    def prepare_context_volume(self, context: IssueContext, 
                              execution_config: ExecutionConfig) -> Tuple[str, str]:
        """Prepare and create context volume directory.
        
        Creates a temporary directory with JSON context files that will be
        mounted into the container at /phixr-context.
        
        Args:
            context: Issue context from GitLab/GitHub
            execution_config: Execution configuration
            
        Returns:
            Tuple of (volume_path, volume_name)
            
        Raises:
            ValueError: If context is invalid or too large
        """
        session_id = execution_config.session_id
        
        # Validate context size
        context_json = context.model_dump_json()
        if len(context_json.encode()) > self.config.context_volume_size:
            raise ValueError(
                f"Context too large ({len(context_json)} bytes > "
                f"{self.config.context_volume_size} bytes)"
            )
        
        # Create temporary directory
        temp_dir = tempfile.TemporaryDirectory(prefix=f"phixr-context-{session_id}-")
        volume_path = Path(temp_dir.name)
        
        logger.info(f"Creating context volume at {volume_path}")
        
        # Write issue context
        issue_file = volume_path / "issue.json"
        issue_file.write_text(context_json, encoding="utf-8")
        logger.debug(f"Wrote issue context to {issue_file}")
        
        # Write execution configuration
        exec_file = volume_path / "config.json"
        exec_config_dict = execution_config.model_dump()
        exec_file.write_text(json.dumps(exec_config_dict, indent=2, default=str), encoding="utf-8")
        logger.debug(f"Wrote execution config to {exec_file}")
        
        # Write repository metadata
        repo_file = volume_path / "repository.json"
        repo_metadata = {
            "url": context.repo_url,
            "name": context.repo_name,
            "language": context.language,
            "structure": context.structure,
            "git_provider": self.config.git_provider_type,
            "git_provider_url": self.config.git_provider_url,
        }
        repo_file.write_text(json.dumps(repo_metadata, indent=2), encoding="utf-8")
        logger.debug(f"Wrote repository metadata to {repo_file}")
        
        # Write initial instructions
        instructions_file = volume_path / "instructions.md"
        instructions = self._generate_instructions(context, execution_config)
        instructions_file.write_text(instructions, encoding="utf-8")
        logger.debug(f"Wrote instructions to {instructions_file}")
        
        # Store reference for cleanup later
        volume_name = f"phixr-context-{session_id}"
        self.temp_dirs[volume_name] = volume_path
        
        logger.info(f"Context volume prepared: {volume_name}")
        return str(volume_path), volume_name
    
    def _generate_instructions(self, context: IssueContext, 
                              execution_config: ExecutionConfig) -> str:
        """Generate initial instructions for OpenCode.
        
        Args:
            context: Issue context
            execution_config: Execution configuration
            
        Returns:
            Markdown instructions string
        """
        mode_str = "analysis and exploration (read-only)" if execution_config.mode == ExecutionMode.PLAN else "development"
        
        instructions = f"""# Phixr OpenCode Session Instructions

## Issue
**ID:** {context.issue_id}
**Title:** {context.issue_title}

### Description
{context.issue_description}

### Labels
{', '.join(context.issue_labels) if context.issue_labels else '(none)'}

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

### Files & Context
Repository structure has been provided. Review the code organization before starting.

---

Generated at {datetime.utcnow().isoformat()}Z by Phixr
"""
        return instructions
    
    def create_environment_variables(self, context: IssueContext,
                                    execution_config: ExecutionConfig,
                                    git_token: str) -> Dict[str, str]:
        """Create environment variables for container.
        
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
            "OPENCODE_MODE": execution_config.mode.value,
            "OPENCODE_MODEL": execution_config.model,
            "OPENCODE_TEMPERATURE": str(execution_config.temperature),
            
            # Container behavior
            "OPENCODE_TELEMETRY": "0",
            "OPENCODE_LOG_LEVEL": self.config.log_level,
        }
        
        # Add initial prompt if provided
        if execution_config.initial_prompt:
            env_vars["OPENCODE_INITIAL_PROMPT"] = execution_config.initial_prompt
        
        return env_vars
    
    def cleanup_context_volume(self, volume_name: str) -> bool:
        """Clean up temporary context volume.
        
        Args:
            volume_name: Name of the volume to clean up
            
        Returns:
            True if cleanup successful, False otherwise
        """
        if volume_name not in self.temp_dirs:
            logger.warning(f"Volume {volume_name} not found in cleanup registry")
            return False
        
        try:
            volume_path = self.temp_dirs[volume_name]
            if volume_path.exists():
                import shutil
                shutil.rmtree(volume_path, ignore_errors=True)
                logger.info(f"Cleaned up context volume: {volume_name}")
            del self.temp_dirs[volume_name]
            return True
        except Exception as e:
            logger.error(f"Error cleaning up context volume {volume_name}: {e}")
            return False
    
    def cleanup_all(self) -> None:
        """Clean up all temporary volumes."""
        for volume_name in list(self.temp_dirs.keys()):
            self.cleanup_context_volume(volume_name)
    
    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup_all()


if __name__ == "__main__":
    # Example usage
    config = SandboxConfig()
    injector = ContextInjector(config)
    
    # Create a sample context
    from phixr.models.issue_context import IssueContext
    
    sample_context = IssueContext(
        issue_id=123,
        issue_title="Test Issue",
        issue_description="Test description",
        repo_url="https://github.com/test/repo.git",
        repo_name="repo",
        language="python",
        structure={"src/": "Source code"},
        issue_labels=["feature"],
    )
    
    exec_config = ExecutionConfig(
        session_id="test-sess-123",
        issue_id=123,
        repo_url="https://github.com/test/repo.git",
        branch="ai-work/123",
    )
    
    try:
        volume_path, volume_name = injector.prepare_context_volume(sample_context, exec_config)
        print(f"✓ Context volume prepared: {volume_name}")
        print(f"  Path: {volume_path}")
        
        env_vars = injector.create_environment_variables(sample_context, exec_config, "test-token")
        print(f"✓ Environment variables created: {len(env_vars)} vars")
    except Exception as e:
        print(f"✗ Error: {e}")
