import asyncio
import os
import logging
import time
import signal
import sys

from app.services.async_docker import AsyncLogMonitor
from app.services.sync_docker import SyncDocker
from app.services.spt_server import SPTServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FikaMonitor:
    def __init__(
        self,
        headless_container_name: str,
        server_container_name: str,
        shutdown_delay: int = 300
    ):
        self.headless_container_name = headless_container_name
        self.server_container_name = server_container_name
        self.shutdown_delay = shutdown_delay
        
        # State tracking
        self.current_time: float = time.time()
        self.last_activity_time: float = time.time()
        self.shutdown_time: float = self.last_activity_time + self.shutdown_delay
        self.is_running = True

        self.waiting_for_headless_start: bool = False

        self.sync_docker = SyncDocker()
        self.spt_server = SPTServer(self.server_container_name)
                
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.is_running = False

    async def activity_detected(self, msg: str):
        logger.info(f"Activity detected: {msg}")
        self.last_activity_time = self.current_time
        self.shutdown_time = self.last_activity_time + self.shutdown_delay

        # immediately start container if not running
        container_status = self.sync_docker.get_container_status(self.headless_container_name)
        if container_status != "running":
            self.waiting_for_headless_start = True
            self.sync_docker.start_container(self.headless_container_name)
            await self.spt_server.fika_notification('Player activity detected, starting headless client...', 0)

    # TODO: monitor headless client logs as well?
    # One issue is reconnecting to the docker container on every restart
    # Another is the headless client isn't as reliable
    # Logs are not as consistent as the server logs
    # TODO: reconnect if for some reason we need to 
    async def monitor_logs_task(self):
        """Task to monitor logs for login events."""
        async with AsyncLogMonitor(self.server_container_name) as monitor:
            async for activity_message in monitor.monitor_for_activity():
                if not self.is_running:
                    break
                
                if activity_message == 'headless_started':
                    if self.waiting_for_headless_start:
                        await self.spt_server.fika_notification('Headless client is available.', 5)
                        self.waiting_for_headless_start = False
                else:
                    # Update last activity time
                    await self.activity_detected(msg=activity_message)

                await asyncio.sleep(0)
    
    async def check_players_api(self) -> int:
        """Check for players via API."""
        players = await self.spt_server.fetch_online_players()
        if len(players) > 0:  # Non-empty list
            logger.info(f"API check: {len(players)} players online")
            return len(players)
        else:
            logger.info("API check: No players online")
        return 0

    async def maintenance_loop(self):
        """Main maintenance loop - checks API and shuts down the container."""
        
        while self.is_running:

            await asyncio.sleep(5) # relax

            try:
                self.current_time = time.time()

                # if it's not time to shutdown, we do nothing
                if self.current_time < self.shutdown_time:
                    continue

                container_status = self.sync_docker.get_container_status(self.headless_container_name)
                # if the container is not running, do nothing
                if container_status != "running":
                    continue
                
                # it's time to shutdown, do a final check
                players_online = await self.check_players_api()
                if players_online > 0:
                    await self.activity_detected(msg=f'{players_online} players online, aborting shutdown')
                    continue
                
                if container_status == "running":
                    logger.info(f"No activity for {self.shutdown_delay}s, {players_online} players online, stopping container")
                    self.sync_docker.stop_container(self.headless_container_name)
                else:
                    logger.warning(f"Intended to shutdown but the container was not running, status: {container_status}")

                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}")
                await asyncio.sleep(10)  # Back off on error

    async def wait_for_initialization(self, timeout: int = 30):
        """Wait for initial conditions to be met."""
        logger.info("Waiting for fika-server container...")
        
        start_time = time.time()
        while self.is_running and (time.time() - start_time) < timeout:
            if await self.spt_server.ping_server():
                return True
            
            await asyncio.sleep(2)
        
        logger.warning(f"fika-server container not found after {timeout}s")
        return False
    
    async def run(self):
        """Main entry point."""
        logger.info(f"Starting fika monitor for container '{self.headless_container_name}'")
        logger.info(f"Shutdown delay: {self.shutdown_delay}s")
        
        if not await self.wait_for_initialization():
            logger.error("Failed to initialize, exiting")
            return

        # Get initial container status
        initial_status = self.sync_docker.get_container_status(self.headless_container_name)
        logger.info(f"Initial container status: {initial_status}")

        # Initialize last activity time if container is already running
        if initial_status == "running":
            self.last_activity_time = time.time()
            logger.info(f"Container already running, tracking activity from now")
        
        # Start tasks
        log_monitor_task = asyncio.create_task(self.monitor_logs_task())
        maintenance_task = asyncio.create_task(self.maintenance_loop())

        # Wait for tasks to complete
        try:
            await asyncio.gather(log_monitor_task, maintenance_task)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")
        finally:
            # Cancel tasks
            log_monitor_task.cancel()
            maintenance_task.cancel()
            
            # Wait for tasks to finish cancellation
            await asyncio.gather(
                log_monitor_task,
                maintenance_task,
                return_exceptions=True
            )
            
            logger.info("fika monitor stopped")


def main():
    """Main function to run the manager with environment variable support."""
    config = {
        "headless_container_name": os.getenv("HEADLESS_CONTAINER_NAME", "fika-headless"),
        "server_container_name": os.getenv("SERVER_CONTAINER_NAME", "fika-server"),
        "shutdown_delay": int(os.getenv("SHUTDOWN_DELAY", "300"))
    }
    
    manager = FikaMonitor(**config)
    
    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
