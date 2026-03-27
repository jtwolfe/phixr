"""Access Management Service.

Handles SSL certificate management and PAT token rotation for GitLab access.
Ensures the bot maintains its own access credentials independently.
"""

import asyncio
import logging
import subprocess
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import base64

from phixr.utils.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)

class AccessManagementService:
    """Service for managing SSL certificates and PAT tokens.

    Features:
    - Automatic SSL certificate download and trust
    - Daily PAT expiration monitoring (7-day warning)
    - Automatic PAT rotation using root token
    - Self-maintaining access credentials
    """

    def __init__(self,
                 gitlab_url: str,
                 root_token: str,
                 bot_username: str = "phixr-bot",
                 cert_dir: Path = Path("/usr/local/share/ca-certificates"),
                 check_interval_hours: int = 24):
        """Initialize access management service.

        Args:
            gitlab_url: GitLab instance URL
            root_token: Root user PAT for administrative access
            bot_username: Bot user username
            cert_dir: Directory for SSL certificates
            check_interval_hours: How often to check PAT expiration
        """
        self.gitlab_url = gitlab_url
        self.root_token = root_token
        self.bot_username = bot_username
        self.cert_dir = cert_dir
        self.check_interval_hours = check_interval_hours

        # Initialize GitLab clients
        self.root_client = GitLabClient(gitlab_url, root_token)

        # Certificate paths
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        self.gitlab_cert_file = self.cert_dir / "gitlab.crt"

        # PAT management
        self.bot_token: Optional[str] = None
        self.bot_token_expires_at: Optional[datetime] = None
        self.last_check: Optional[datetime] = None

        # Background task
        self.monitor_task: Optional[asyncio.Task] = None

        logger.info(f"Access management service initialized for {gitlab_url}")

    async def start_monitoring(self) -> None:
        """Start the background monitoring task."""
        if self.monitor_task and not self.monitor_task.done():
            logger.warning("Monitoring task already running")
            return

        logger.info("Starting access monitoring task")
        self.monitor_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self) -> None:
        """Stop the background monitoring task."""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
            logger.info("Access monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that runs periodically."""
        while True:
            try:
                await self._perform_maintenance_checks()
                await asyncio.sleep(self.check_interval_hours * 3600)  # Convert hours to seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(300)  # Retry in 5 minutes on error

    async def _perform_maintenance_checks(self) -> None:
        """Perform all maintenance checks."""
        logger.info("Performing access maintenance checks")

        try:
            # Ensure SSL certificates are up to date
            await self._ensure_ssl_certificates()

            # Check and rotate PAT if needed
            await self._check_and_rotate_pat()

            self.last_check = datetime.utcnow()
            logger.info("Access maintenance checks completed")

        except Exception as e:
            logger.error(f"Error during maintenance checks: {e}")
            raise

    async def _ensure_ssl_certificates(self) -> None:
        """Ensure GitLab SSL certificates are downloaded and trusted."""
        try:
            # Check if GitLab uses HTTPS
            if not self.gitlab_url.startswith("https://"):
                logger.info("GitLab uses HTTP, no SSL certificate needed")
                # Configure git to skip SSL verification for this host
                await self._configure_git_ssl_bypass()
                return

            # Extract hostname
            hostname = self._extract_hostname(self.gitlab_url)
            if not hostname:
                logger.error(f"Could not extract hostname from {self.gitlab_url}")
                return

            # Download certificate
            cert_downloaded = await self._download_ssl_certificate(hostname)
            if cert_downloaded:
                # Update CA certificates
                await self._update_ca_certificates()

            # Configure git SSL settings
            await self._configure_git_ssl_settings()

        except Exception as e:
            logger.error(f"Error ensuring SSL certificates: {e}")

    async def _download_ssl_certificate(self, hostname: str) -> bool:
        """Download SSL certificate from GitLab."""
        try:
            # Use openssl to get the certificate
            cmd = [
                "openssl", "s_client", "-connect", f"{hostname}:443",
                "-servername", hostname, "-showcerts"
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                input=b""  # Empty input to close connection
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.warning(f"Failed to connect to {hostname}:443")
                return False

            # Extract the certificate (first certificate in chain)
            output = stdout.decode()
            cert_start = output.find("-----BEGIN CERTIFICATE-----")
            cert_end = output.find("-----END CERTIFICATE-----", cert_start) + 25

            if cert_start == -1 or cert_end == -1:
                logger.warning("No certificate found in SSL output")
                return False

            certificate = output[cert_start:cert_end]

            # Save certificate
            async with asyncio.get_event_loop().run_in_executor(None, self._write_cert_file, certificate):
                logger.info(f"SSL certificate downloaded and saved to {self.gitlab_cert_file}")
                return True

        except Exception as e:
            logger.error(f"Error downloading SSL certificate: {e}")
            return False

    def _write_cert_file(self, certificate: str) -> None:
        """Write certificate to file (runs in executor to avoid blocking)."""
        with open(self.gitlab_cert_file, 'w') as f:
            f.write(certificate)

    async def _update_ca_certificates(self) -> None:
        """Update the system's CA certificate store."""
        try:
            # Run update-ca-certificates
            process = await asyncio.create_subprocess_exec(
                "update-ca-certificates",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info("CA certificates updated successfully")
            else:
                logger.error(f"Failed to update CA certificates: {stderr.decode()}")

        except Exception as e:
            logger.error(f"Error updating CA certificates: {e}")

    async def _configure_git_ssl_settings(self) -> None:
        """Configure git SSL settings."""
        try:
            # Set git to use system CA certificates
            await self._run_git_command(["config", "--global", "http.sslCAInfo", "/etc/ssl/certs/ca-certificates.crt"])

            # For development, also disable SSL verification for localhost
            if "localhost" in self.gitlab_url:
                await self._run_git_command(["config", "--global", "http.sslVerify", "false"])

        except Exception as e:
            logger.error(f"Error configuring git SSL settings: {e}")

    async def _configure_git_ssl_bypass(self) -> None:
        """Configure git to bypass SSL for HTTP-only GitLab."""
        try:
            hostname = self._extract_hostname(self.gitlab_url)
            if hostname:
                await self._run_git_command([
                    "config", "--global",
                    f"http.{self.gitlab_url}.sslVerify", "false"
                ])
                logger.info(f"Configured git to skip SSL verification for {self.gitlab_url}")
        except Exception as e:
            logger.error(f"Error configuring git SSL bypass: {e}")

    async def _run_git_command(self, args: list) -> None:
        """Run a git command."""
        process = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise Exception(f"git command failed: {stderr.decode()}")

    async def _check_and_rotate_pat(self) -> None:
        """Check PAT expiration and rotate if needed."""
        try:
            # Get current bot user PAT info
            bot_user = await self.root_client.get_user(self.bot_username)
            if not bot_user:
                logger.error(f"Bot user {self.bot_username} not found")
                return

            # Get bot user's PATs
            pats = await self.root_client.get_user_pats(bot_user['id'])

            # Check if we got a valid response
            if pats is None:
                logger.warning("PAT API not available or insufficient permissions - using static token")
                return

            # Find the active PAT for our bot
            active_pat = None
            expires_soon = False

            for pat in pats:
                if pat.get('active', False) and 'phixr' in pat.get('name', '').lower():
                    active_pat = pat
                    expires_at = pat.get('expires_at')
                    if expires_at:
                        expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        days_until_expiry = (expires_dt - datetime.utcnow()).days

                        if days_until_expiry <= 7:
                            expires_soon = True
                            logger.warning(f"PAT expires in {days_until_expiry} days: {expires_at}")

                    break

            if not active_pat or expires_soon:
                logger.info("Creating new PAT for bot user")
                await self._create_new_pat(bot_user['id'])
            else:
                logger.info("PAT is still valid")

        except Exception as e:
            logger.error(f"Error checking PAT: {e}")
            # Don't fail completely - just log and continue with static token

    async def _create_new_pat(self, user_id: int) -> None:
        """Create a new PAT for the bot user."""
        try:
            # Generate PAT name with timestamp
            pat_name = f"phixr-bot-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

            # Set expiration to 90 days from now
            expires_at = (datetime.utcnow() + timedelta(days=90)).date().isoformat()

            # Create new PAT
            new_pat = await self.root_client.create_user_pat(
                user_id=user_id,
                name=pat_name,
                expires_at=expires_at,
                scopes=['api', 'read_repository', 'write_repository']
            )

            if new_pat and 'token' in new_pat:
                # Revoke old PAT if it exists
                if self.bot_token:
                    await self._revoke_old_pat(user_id)

                # Store new token
                self.bot_token = new_pat['token']
                self.bot_token_expires_at = datetime.fromisoformat(expires_at)

                # Save token to environment or config
                await self._save_bot_token()

                logger.info(f"New PAT created for bot user, expires: {expires_at}")
            else:
                logger.error("Failed to create new PAT")

        except Exception as e:
            logger.error(f"Error creating new PAT: {e}")

    async def _revoke_old_pat(self, user_id: int) -> None:
        """Revoke the old bot PAT."""
        try:
            # Get all PATs for the user
            pats = await self.root_client.get_user_pats(user_id)

            # Revoke PATs that are not the current one and contain 'phixr' in name
            for pat in pats:
                if (pat.get('active', False) and
                    'phixr' in pat.get('name', '').lower() and
                    pat.get('name') != f"phixr-bot-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"):
                    await self.root_client.revoke_user_pat(user_id, pat['id'])
                    logger.info(f"Revoked old PAT: {pat['name']}")

        except Exception as e:
            logger.error(f"Error revoking old PAT: {e}")

    async def _save_bot_token(self) -> None:
        """Save the bot token to persistent storage."""
        try:
            # For now, save to a file that can be loaded by the main application
            token_file = Path("/app/.phixr_bot_token")
            await asyncio.get_event_loop().run_in_executor(None, self._write_token_file, token_file)
            logger.info("Bot token saved to persistent storage")

        except Exception as e:
            logger.error(f"Error saving bot token: {e}")

    def _write_token_file(self, token_file: Path) -> None:
        """Write token to file."""
        with open(token_file, 'w') as f:
            f.write(self.bot_token)

    async def get_current_bot_token(self) -> Optional[str]:
        """Get the current bot token."""
        return self.bot_token

    async def load_saved_bot_token(self) -> Optional[str]:
        """Load saved bot token from persistent storage."""
        try:
            token_file = Path("/app/.phixr_bot_token")
            if token_file.exists():
                await asyncio.get_event_loop().run_in_executor(None, self._read_token_file, token_file)
                return self.bot_token
        except Exception as e:
            logger.error(f"Error loading saved bot token: {e}")
        return None

    def _read_token_file(self, token_file: Path) -> str:
        """Read token from file."""
        with open(token_file, 'r') as f:
            self.bot_token = f.read().strip()
            return self.bot_token

    def _extract_hostname(self, url: str) -> Optional[str]:
        """Extract hostname from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.hostname
        except Exception:
            return None

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of access management."""
        status = {
            "ssl_certificates": await self._check_ssl_status(),
            "pat_status": await self._check_pat_status(),
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "monitoring_active": self.monitor_task is not None and not self.monitor_task.done()
        }

        # Overall health
        status["healthy"] = all([
            status["ssl_certificates"]["healthy"],
            status["pat_status"]["healthy"]
        ])

        return status

    async def _check_ssl_status(self) -> Dict[str, Any]:
        """Check SSL certificate status."""
        try:
            cert_exists = await asyncio.get_event_loop().run_in_executor(None, self.gitlab_cert_file.exists)
            return {
                "healthy": True,
                "certificate_exists": cert_exists,
                "certificate_path": str(self.gitlab_cert_file)
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }

    async def _check_pat_status(self) -> Dict[str, Any]:
        """Check PAT status."""
        try:
            has_token = self.bot_token is not None
            expires_soon = False
            pat_management_available = True

            if self.bot_token_expires_at:
                days_until_expiry = (self.bot_token_expires_at - datetime.utcnow()).days
                expires_soon = days_until_expiry <= 7
            else:
                # If we don't have an expiration date, PAT management might not be available
                pat_management_available = False

            return {
                "healthy": has_token and (not pat_management_available or not expires_soon),
                "has_token": has_token,
                "expires_soon": expires_soon,
                "pat_management_available": pat_management_available,
                "expires_at": self.bot_token_expires_at.isoformat() if self.bot_token_expires_at else None
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }