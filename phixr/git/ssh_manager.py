"""SSH key management for Git operations.

Manages SSH keys for repository cloning and pushing, supporting both
configured keys and managed keys via access manager.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GitSSHManager:
    """Manages SSH keys for Git operations.
    
    Features:
    - Support for configured SSH keys (path + optional passphrase)
    - SSH known_hosts management
    - Git SSH URL support
    - Container-aware path handling
    """
    
    def __init__(self, ssh_key_path: str = "/root/.ssh/id_rsa", 
                 ssh_key_passphrase: str = ""):
        """Initialize SSH manager.
        
        Args:
            ssh_key_path: Path to SSH private key
            ssh_key_passphrase: Optional SSH key passphrase
        """
        self.ssh_key_path = Path(ssh_key_path)
        self.ssh_key_passphrase = ssh_key_passphrase
        self.ssh_dir = self.ssh_key_path.parent
        self.known_hosts = self.ssh_dir / "known_hosts"
        
        logger.info(f"SSH Manager initialized: key={self.ssh_key_path}")
        
        # Ensure SSH directory exists
        self._ensure_ssh_directory()
    
    def _ensure_ssh_directory(self) -> None:
        """Ensure SSH directory exists with proper permissions."""
        if not self.ssh_dir.exists():
            try:
                self.ssh_dir.mkdir(parents=True, mode=0o700)
                logger.info(f"Created SSH directory: {self.ssh_dir}")
            except Exception as e:
                logger.warning(f"Failed to create SSH directory: {e}")
        else:
            # Ensure proper permissions (0o700 = rwx------)
            try:
                self.ssh_dir.chmod(0o700)
            except Exception as e:
                logger.warning(f"Failed to set SSH directory permissions: {e}")
    
    def configure_ssh_for_host(self, host: str) -> bool:
        """Configure SSH for a specific Git host (GitLab, GitHub, etc).
        
        Adds host to known_hosts to avoid interactive SSH prompts.
        
        Args:
            host: Hostname (e.g., 'gitlab.com', 'localhost', '192.168.1.1')
            
        Returns:
            True if configuration succeeded, False otherwise
        """
        try:
            # Skip for localhost/127.0.0.1 - they don't have stable keys
            if host in ['localhost', '127.0.0.1'] or host.startswith('172.'):
                logger.debug(f"Skipping known_hosts for local dev host: {host}")
                return True
            
            # Run ssh-keyscan to get the host key
            logger.debug(f"Running ssh-keyscan for {host}...")
            result = subprocess.run(
                ["ssh-keyscan", "-H", host],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning(f"ssh-keyscan failed for {host}: {result.stderr}")
                return False
            
            # Append to known_hosts if not already present
            if result.stdout:
                try:
                    with open(self.known_hosts, "a") as f:
                        f.write(result.stdout)
                        if not result.stdout.endswith('\n'):
                            f.write('\n')
                    
                    # Set proper permissions
                    self.known_hosts.chmod(0o600)
                    logger.info(f"Added {host} to known_hosts")
                    return True
                except Exception as e:
                    logger.warning(f"Failed to write to known_hosts: {e}")
                    return False
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.warning(f"ssh-keyscan timeout for {host}")
            return False
        except Exception as e:
            logger.warning(f"Failed to configure SSH for {host}: {e}")
            return False
    
    def get_ssh_command_env(self) -> dict:
        """Get environment variables for SSH operations.
        
        Returns:
            Dictionary of environment variables to use with git commands
        """
        env = os.environ.copy()
        
        # Configure SSH_AUTH_SOCK if available
        if "SSH_AUTH_SOCK" not in env:
            logger.debug("SSH_AUTH_SOCK not set, SSH agent may not be available")
        
        # Set GIT_SSH_COMMAND to use our key
        ssh_cmd = f"ssh -i {self.ssh_key_path} -o StrictHostKeyChecking=accept-new"
        
        if self.ssh_key_path.exists():
            # File exists, use it
            env["GIT_SSH_COMMAND"] = ssh_cmd
            logger.debug(f"Set GIT_SSH_COMMAND to use key: {self.ssh_key_path}")
        else:
            # Key doesn't exist yet - just log a warning
            logger.warning(f"SSH key not found: {self.ssh_key_path}")
        
        return env
    
    def setup_git_config(self) -> bool:
        """Configure global git settings for SSH.
        
        Returns:
            True if configuration succeeded, False otherwise
        """
        try:
            # Configure git to use our SSH key
            subprocess.run(
                ["git", "config", "--global", "core.sshCommand", 
                 f"ssh -i {self.ssh_key_path} -o StrictHostKeyChecking=accept-new"],
                check=True
            )
            logger.info(f"Configured git to use SSH key: {self.ssh_key_path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to configure git: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error configuring git: {e}")
            return False
    
    def has_ssh_key(self) -> bool:
        """Check if SSH key is available.
        
        Returns:
            True if SSH key exists and is readable, False otherwise
        """
        if not self.ssh_key_path.exists():
            return False
        
        try:
            # Try to read the key to verify it's accessible
            with open(self.ssh_key_path, 'r') as f:
                content = f.read()
                return "BEGIN" in content and ("RSA" in content or "OPENSSH" in content or "EC" in content)
        except Exception as e:
            logger.warning(f"Error reading SSH key: {e}")
            return False
    
    def extract_host_from_url(self, repo_url: str) -> Optional[str]:
        """Extract hostname from Git URL.
        
        Args:
            repo_url: Git repository URL (SSH or HTTPS format)
            
        Returns:
            Hostname or None if unable to extract
        """
        try:
            # SSH format: git@example.com:user/repo.git
            if repo_url.startswith("git@"):
                host = repo_url.split("@")[1].split(":")[0]
                return host
            
            # HTTPS format: https://example.com/user/repo.git
            if "://" in repo_url:
                host = repo_url.split("://")[1].split("/")[0]
                # Remove port if present
                if ":" in host:
                    host = host.split(":")[0]
                return host
            
            return None
        except Exception as e:
            logger.warning(f"Failed to extract host from URL: {e}")
            return None


def setup_git_ssh_for_url(repo_url: str, ssh_manager: GitSSHManager) -> bool:
    """Setup Git SSH configuration for a specific repository URL.
    
    Args:
        repo_url: Repository URL
        ssh_manager: SSH manager instance
        
    Returns:
        True if setup succeeded, False otherwise
    """
    try:
        # Extract host from URL
        host = ssh_manager.extract_host_from_url(repo_url)
        if not host:
            logger.warning(f"Could not extract host from URL: {repo_url}")
            return False
        
        # Configure SSH for this host
        return ssh_manager.configure_ssh_for_host(host)
        
    except Exception as e:
        logger.error(f"Failed to setup Git SSH for {repo_url}: {e}")
        return False
