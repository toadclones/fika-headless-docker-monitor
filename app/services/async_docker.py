import asyncio
import logging
import traceback
import time
import re

from typing import AsyncGenerator
from aiodocker import Docker
from aiodocker.containers import DockerContainer
from aiohttp import ClientSession, UnixConnector, ClientTimeout

logger = logging.getLogger(__name__)

class AsyncLogMonitor:
    """Asynchronous log monitor using aiodocker."""
    
    def __init__(self, container_name: str):
        self.container_name = container_name
        self.docker = Docker(
            session=ClientSession(
                connector=UnixConnector('/var/run/docker.sock'),
                timeout=ClientTimeout(total=None, connect=30, sock_connect=30, sock_read=None)
            )
        )
        self.container: DockerContainer = None
        self.is_running = True
        self.start_time = time.time()

        # TODO: put this in env variables?
        self.activity_messages = [
            '/launcher/profile/login', # indicates a player is logging in
            '/launcher/server/version', # indicates player is in-game, may be unnecessary
            '/fika/presence/set', # indicates menu/stach/hideout activity
            '/fika/update/ping' # indicates raid activity
        ]

        
    async def connect(self):
        """Connect to the Docker container."""
        try:
            # Get the container
            containers = await self.docker.containers.list()
            for container in containers:
                container_info = await container.show()
                if container_info['Name'].lstrip('/') == self.container_name:
                    self.container = container
                    logger.info(f"Connected to container: {self.container_name}")
                    return
            
            logger.error(f"Container not found: {self.container_name}")
            raise ValueError(f"Container not found: {self.container_name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to container: {e}")
            raise
    
    async def stream_logs(self) -> AsyncGenerator[str, None]:
        """Stream logs from the container asynchronously."""
        if not self.container:
            await self.connect()
        
        try:
            # Start streaming logs
            async for line in self.container.log(
                stdout=True,
                stderr=True,
                follow=True,
                timestamps=False,
                since=self.start_time
            ):
                if not self.is_running:
                    break
                yield line
                
        except asyncio.CancelledError:
            logger.info("Log streaming cancelled")
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error streaming logs: {e}")
    
    async def monitor_for_activity(self) -> AsyncGenerator[str, None]:
        """Monitor logs for activity."""
        async for line in self.stream_logs():
            for activity_message in self.activity_messages:
                if activity_message in line:
                    yield activity_message
            
            if re.search('(headless_).*(has connected)', line):
                yield 'headless_started'
            await asyncio.sleep(0)
    
    async def close(self):
        """Clean up resources."""
        self.is_running = False
        await self.docker.close()
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()