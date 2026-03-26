"""Docker SDK wrapper with Phixr-specific functionality."""

import logging
from typing import Dict, Tuple, Optional, List
import docker
from docker.errors import DockerException, ImageNotFound, ContainerError
from docker.types import IPAMConfig, IPAMPool

from phixr.config.sandbox_config import SandboxConfig

logger = logging.getLogger(__name__)


class DockerClientWrapper:
    """Wrapper around Docker SDK for Phixr container management."""
    
    def __init__(self, config: SandboxConfig):
        """Initialize Docker client.
        
        Args:
            config: Sandbox configuration
            
        Raises:
            DockerException: If Docker daemon cannot be reached
        """
        self.config = config
        
        try:
            self.client = docker.DockerClient(base_url=config.docker_host)
            # Verify connection
            self.client.ping()
            logger.info(f"Connected to Docker at {config.docker_host}")
        except DockerException as e:
            logger.error(f"Failed to connect to Docker: {e}")
            raise
    
    def ensure_network(self) -> str:
        """Ensure Docker network exists.
        
        Creates the Phixr network if it doesn't exist.
        
        Returns:
            Network name
            
        Raises:
            DockerException: If network creation fails
        """
        network_name = self.config.docker_network
        
        try:
            # Try to get existing network
            network = self.client.networks.get(network_name)
            logger.info(f"Using existing Docker network: {network_name}")
            return network_name
        except docker.errors.NotFound:
            # Network doesn't exist, create it
            try:
                ipam_pool = IPAMPool(subnet="10.0.9.0/24")
                ipam_config = IPAMConfig(pool_configs=[ipam_pool])
                
                network = self.client.networks.create(
                    network_name,
                    driver="bridge",
                    ipam=ipam_config,
                    options={
                        "com.docker.network.bridge.enable_ip_masquerade": "true",
                        "com.docker.network.driver.mtu": "1500",
                    }
                )
                logger.info(f"Created Docker network: {network_name}")
                return network_name
            except DockerException as e:
                logger.error(f"Failed to create network {network_name}: {e}")
                raise
    
    def build_image(self, dockerfile_path: str, tag: str, 
                   build_args: Optional[Dict[str, str]] = None) -> str:
        """Build Docker image from Dockerfile.
        
        Args:
            dockerfile_path: Path to Dockerfile
            tag: Image tag (e.g., "phixr/opencode:latest")
            build_args: Build arguments to pass to Docker
            
        Returns:
            Image ID
            
        Raises:
            DockerException: If build fails
        """
        if build_args is None:
            build_args = {}
        
        try:
            logger.info(f"Building Docker image: {tag} from {dockerfile_path}")
            image, build_logs = self.client.images.build(
                path=str(dockerfile_path),
                tag=tag,
                buildargs=build_args,
                rm=True,
            )
            
            # Log build output
            for log in build_logs:
                if "stream" in log:
                    logger.debug(log["stream"].strip())
            
            logger.info(f"Successfully built image: {tag} ({image.id})")
            return image.id
        except DockerException as e:
            logger.error(f"Failed to build image {tag}: {e}")
            raise
    
    def run_container(self, image: str, mounts: Dict[str, Dict],
                     env: Dict[str, str], timeout: int = 1800,
                     memory_limit: Optional[str] = None) -> Tuple[str, int, str]:
        """Run container and return container_id, exit_code, logs.
        
        Args:
            image: Image name/tag
            mounts: Volume mounts {container_path: {"bind": host_path, "mode": "rw"}}
            env: Environment variables
            timeout: Container timeout in seconds
            memory_limit: Memory limit (e.g., "2g")
            
        Returns:
            Tuple of (container_id, exit_code, logs)
            
        Raises:
            DockerException: If container execution fails
        """
        try:
            # Ensure network exists
            network = self.ensure_network()
            
            # Pull image if not present
            try:
                self.client.images.get(image)
            except ImageNotFound:
                logger.info(f"Pulling Docker image: {image}")
                self.client.images.pull(image)
            
            # Prepare volume binds
            volumes = [
                f"{spec['bind']}:{path}:{'ro' if spec.get('mode') == 'ro' else 'rw'}"
                for path, spec in mounts.items()
            ]
            
            # Prepare container kwargs
            container_kwargs = {
                "detach": True,
                "environment": env,
                "working_dir": "/workspace",
                "stdin_open": True,
                "tty": True,
                "network": network,
                "volumes": volumes,
            }
            
            if memory_limit:
                try:
                    # Convert memory limit to bytes
                    mem_bytes = self.config.get_docker_memory_limit()
                    container_kwargs["mem_limit"] = mem_bytes
                except ValueError as e:
                    logger.warning(f"Invalid memory limit: {e}")
            
            container_kwargs["cpu_quota"] = int(self.config.cpu_limit * 100000)
            
            # Create and run container using create + start approach
            logger.info(f"Running container from image: {image}")
            
            # Create container first
            container = self.client.containers.create(
                image,
                **container_kwargs,
            )
            
            # Start the container
            container.start()
            
            container_id = container.id[:12]
            logger.info(f"Container started: {container_id}")
            
            # Wait for container to finish (with timeout)
            try:
                exit_code = container.wait(timeout=timeout)
                if isinstance(exit_code, dict):
                    exit_code = exit_code.get("StatusCode", 1)
            except Exception as e:
                logger.warning(f"Container timeout or error: {e}")
                container.kill()
                exit_code = 124  # Timeout exit code
            
            # Get logs
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="ignore")
            
            # Cleanup container
            try:
                container.remove(force=True)
            except Exception as e:
                logger.warning(f"Failed to remove container: {e}")
            
            logger.info(f"Container finished with exit code: {exit_code}")
            return container_id, exit_code, logs
            
        except ContainerError as e:
            logger.error(f"Container error: {e}")
            raise
        except DockerException as e:
            logger.error(f"Docker error: {e}")
            raise
    
    def create_volume(self, name: str) -> str:
        """Create named Docker volume.
        
        Args:
            name: Volume name
            
        Returns:
            Volume name
            
        Raises:
            DockerException: If volume creation fails
        """
        try:
            volume = self.client.volumes.create(
                name=name,
                driver="local",
            )
            logger.info(f"Created Docker volume: {name}")
            return volume.name
        except DockerException as e:
            # Volume might already exist
            logger.debug(f"Volume creation note: {e}")
            return name
    
    def get_container_stats(self, container_id: str) -> Optional[dict]:
        """Get container resource stats.
        
        Args:
            container_id: Container ID or name
            
        Returns:
            Stats dictionary or None if container not found
        """
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            
            # Parse stats
            cpu_stats = stats.get("cpu_stats", {})
            memory_stats = stats.get("memory_stats", {})
            
            # Calculate CPU percentage
            cpu_percent = 0.0
            if "cpu_delta" in cpu_stats and "system_cpu_usage" in cpu_stats:
                cpu_delta = cpu_stats["cpu_delta"]
                system_delta = cpu_stats["system_cpu_usage"] - stats.get("precpu_stats", {}).get("system_cpu_usage", 0)
                if system_delta > 0:
                    cpu_percent = (cpu_delta / system_delta) * 100.0
            
            return {
                "container_id": container_id[:12],
                "status": container.status,
                "memory_usage_mb": memory_stats.get("usage", 0) / (1024 ** 2),
                "memory_limit_mb": memory_stats.get("limit", 0) / (1024 ** 2),
                "cpu_percent": cpu_percent,
                "uptime_seconds": int(container.attrs["State"]["StartedAt"].timestamp()),
            }
        except Exception as e:
            logger.warning(f"Failed to get stats for {container_id}: {e}")
            return None
    
    def get_container_logs(self, container_id: str, since: Optional[int] = None) -> str:
        """Get container logs.
        
        Args:
            container_id: Container ID or name
            since: Unix timestamp to get logs since
            
        Returns:
            Log content
        """
        try:
            container = self.client.containers.get(container_id)
            kwargs = {"stdout": True, "stderr": True}
            if since:
                kwargs["since"] = since
            
            logs = container.logs(**kwargs).decode("utf-8", errors="ignore")
            return logs
        except Exception as e:
            logger.warning(f"Failed to get logs for {container_id}: {e}")
            return ""
    
    def close(self) -> None:
        """Close Docker client connection."""
        try:
            self.client.close()
            logger.info("Docker client closed")
        except Exception as e:
            logger.warning(f"Error closing Docker client: {e}")


if __name__ == "__main__":
    # Example usage
    config = SandboxConfig()
    docker_client = DockerClientWrapper(config)
    
    print("✓ Docker client initialized")
    print(f"  Host: {config.docker_host}")
    print(f"  Network: {config.docker_network}")
