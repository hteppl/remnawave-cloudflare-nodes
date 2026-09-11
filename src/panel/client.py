from typing import Any, List

import httpx
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

    async def set_hosts_enabled(self, uuids: List[str], enabled: bool) -> List[HostResponseDto]:
        """Bulk enable/disable hosts.

        Calls the REST endpoint directly to work around an SDK bug: BulkDisable/EnableHostsResponseDto
        are list subclasses not supported by the rapid client's _handle_response parser.
        """
        if not uuids:
            raise ValueError("No host UUIDs provided")
        action = "enable" if enabled else "disable"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/hosts/bulk/{action}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"uuids": [str(u) for u in uuids]},
            )
        response.raise_for_status()
        data = response.json()
        items = data.get("response", []) if isinstance(data, dict) else data
        return [HostResponseDto.model_validate(item) for item in items or []]
