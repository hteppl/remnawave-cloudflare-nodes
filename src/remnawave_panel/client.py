from typing import Any, List
from uuid import UUID

from remnawave import RemnawaveSDK
from remnawave.models import HostResponseDto, NodeResponseDto

from ..utils.logger import get_logger


def _unwrap(response: Any) -> list:
    return getattr(response, "root", None) or []


class RemnawaveClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.logger = get_logger(__name__)
        self.sdk = RemnawaveSDK(base_url=self.api_url, token=self.api_key)

    async def get_nodes(self) -> List[NodeResponseDto]:
        try:
            nodes = _unwrap(await self.sdk.nodes.get_all_nodes())
        except Exception as e:
            self.logger.error(f"Error fetching nodes: {e}")
            raise
        self.logger.debug(f"Fetched {len(nodes)} nodes from {self.api_url}")
        return nodes

    async def get_hosts(self) -> List[HostResponseDto]:
        try:
            hosts = _unwrap(await self.sdk.hosts.get_all_hosts())
        except Exception as e:
            self.logger.error(f"Error fetching hosts: {e}")
            raise
        self.logger.debug(f"Fetched {len(hosts)} hosts")
        return hosts

    async def set_hosts_enabled(self, uuids: List[str], enabled: bool) -> None:
        """Bulk enable/disable hosts; raises on API errors."""
        if not uuids:
            raise ValueError("No host UUIDs provided")
        bulk = self.sdk.hosts_bulk_actions
        action = bulk.enable_hosts if enabled else bulk.disable_hosts
        await action(uuids=[UUID(u) for u in uuids])
