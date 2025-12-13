import logging

import docker
from docker import DockerClient
from docker.errors import NotFound, APIError
from docker.models.containers import Container

logger = logging.getLogger(__name__)

class SyncDocker:
    """Synchronous docker class to make easy yes good."""
    
    def __init__(self):
        self.docker: DockerClient = docker.from_env()

    def get_container(self, container_name: str) -> Container:
        container: Container = self.docker.containers.get(container_name)
        return container

    def get_container_status(self, container_name: str) -> str:
        """Get the status of the Docker container."""
        try:
            container: Container = self.get_container(container_name)
            return container.status
        except NotFound:
            logger.error(f"Container '{container_name}' not found")
            return "not_found"
        except APIError as e:
            logger.error(f"Docker API error: {e}")
            return "error"
        
    def start_container(self, container_name: str):
        """Start the Docker container."""
        try:
            container: Container = self.get_container(container_name)
            if container.status != "running":
                container.start()
                logger.info(f"Started container '{container_name}'")
            else:
                logger.debug(f"Container '{container_name}' is already running")
        except NotFound:
            logger.error(f"Container '{container_name}' not found")
        except APIError as e:
            logger.error(f"Failed to start container: {e}")

    def stop_container(self, container_name: str):
        """Stop the Docker container."""
        try:
            container: Container = self.get_container(container_name)
            if container.status == "running":
                container.stop()
                logger.info(f"Stopped container '{container_name}'")
            else:
                logger.debug(f"Container '{container_name}' is already stopped")
        except NotFound:
            logger.error(f"Container '{container_name}' not found")
        except APIError as e:
            logger.error(f"Failed to stop container: {e}")