import logging

from typing import Any, Dict, List
from aiohttp import ClientError, ClientSession, ClientTimeout

logger = logging.getLogger(__name__)

class SPTServer:
    """
    Class that represents the SPT server. For api access, or whatever

    Warning: If you re-use a client session for multiple requests, you will regret it.
    """
    
    def __init__(self, container_name: str):
        self.container_name = container_name
        self.headers = {
            "responsecompressed": "0",
            "Content-Type": "application/json"
        }

    # TODO: Possibly add pydantic models to validate API responses? perhaps overcomplicate things for no reason?
    async def fetch_online_players(self) -> List[Dict[str, Any]]:
        """Check for connected players via API."""
        try:
            async with ClientSession() as session:
                async with session.get(
                    url=f"https://{self.container_name}:6969/fika/presence/get",
                    headers=self.headers,
                    ssl=False,  # Disable SSL verification (equivalent to -k)
                    timeout=ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        players = await response.json()
                        logger.debug(f"API response: {players}")
                        return players
                    else:
                        logger.warning(f"API returned status {response.status}")
                        return []
        except ClientError as e:
            logger.warning(f"Failed to check player presence: {e}")
            return []
        

    async def ping_server(self) -> bool:
        """Ping the server"""
        try:
            async with ClientSession() as session:
                async with session.get(
                    url=f"https://{self.container_name}:6969/launcher/ping",
                    ssl=False,  # Disable SSL verification (equivalent to -k)
                    timeout=ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return True
                    else:
                        logger.warning(f"Ping returned status {response.status}")
                        return False
        except ClientError as e:
            logger.warning(f"Server did not pong: {e}")
            return False
    

