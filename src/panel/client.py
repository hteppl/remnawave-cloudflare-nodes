from typing import List
from uuid import UUID

from remnawave.models import (
    NodeResponseDto,
    HostResponseDto,
)

from remnawave import RemnawaveSDK
from ..utils.logger import get_logger

import httpx


class RemnawaveClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.logger = get_logger(__name__)
        self.sdk = RemnawaveSDK(base_url=self.api_url, token=self.api_key)

    async def get_nodes(self) -> List[NodeResponseDto]:
        try:
            self.logger.info(f"Fetching nodes from {self.api_url}")

            response = await self.sdk.nodes.get_all_nodes()  # GetAllNodesResponseDto
            nodes_list = response.root if hasattr(response, "root") else []

            self.logger.info(f"Successfully fetched {len(nodes_list)} nodes")
            return nodes_list
        except Exception as e:
            self.logger.error(f"Error fetching nodes: {e}")
            raise

    async def get_hosts(self) -> List[HostResponseDto]:
        try:
            self.logger.info("Fetching hosts from Remnawave")
            response = await self.sdk.hosts.get_all_hosts()  # GetAllHostsResponseDto
            hosts_list = response.root if hasattr(response, "root") else []
            self.logger.info(f"Successfully fetched {len(hosts_list)} hosts")
            return hosts_list
        except Exception as e:
            self.logger.error(f"Error fetching hosts: {e}")
            raise

    async def _bulk_hosts_action(self, uuids: List[str], action: str) -> List[HostResponseDto]:
        """Work around SDK bug: BulkDisable/EnableHostsResponseDto are list subclasses
        not supported by the rapid client's _handle_response parser."""
        if not uuids:
            raise ValueError("No host UUIDs provided")
        self.logger.info(f"{action.capitalize()}ing {len(uuids)} hosts")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/api/hosts/bulk/{action}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"uuids": [str(u) for u in uuids]},
                )
                response.raise_for_status()
                data = response.json()
                # The API returns a list of host objects directly
                if isinstance(data, list):
                    hosts_list = [HostResponseDto.model_validate(item) for item in data]
                elif isinstance(data, dict) and "response" in data:
                    hosts_list = [HostResponseDto.model_validate(item) for item in data["response"]]
                else:
                    hosts_list = []
                self.logger.info(f"Successfully {action}d {len(uuids)} hosts")
                return hosts_list
        except Exception as e:
            self.logger.error(f"Error {action}ing hosts: {e}")
            raise

    async def disable_hosts(self, uuids: List[str]) -> List[HostResponseDto]:
        return await self._bulk_hosts_action(uuids, "disable")

    async def enable_hosts(self, uuids: List[str]) -> List[HostResponseDto]:
        return await self._bulk_hosts_action(uuids, "enable")

    @staticmethod
    def is_node_connected(node: NodeResponseDto) -> bool:
        return node.is_connected

    @staticmethod
    def is_node_disabled(node: NodeResponseDto) -> bool:
        return node.is_disabled

    @staticmethod
    def is_node_healthy(node: NodeResponseDto) -> bool:
        return RemnawaveClient.is_node_connected(node) and not RemnawaveClient.is_node_disabled(node)
